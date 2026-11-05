"""AI-assisted order intake and candidate extraction endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import (
    get_ai_intake_service,
    get_customer_repository,
    get_product_repository,
    require_business_role,
)
from backend.app.repositories.customer_repository import BaseCustomerRepository
from backend.app.repositories.product_repository import BaseProductRepository
from backend.app.schemas.ai_intake import OrderIntakeRequest, OrderIntakeResponse
from backend.app.schemas.auth import BusinessMembership
from backend.app.services.ai_intake import (
    AIConfigurationError,
    AIExtractionError,
    AIIntakeService,
)

router = APIRouter()


@router.post(
    "/ai-intake",
    response_model=OrderIntakeResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract & Match Candidate Order from Message",
    description="Processes raw customer text using a schema-constrained AI provider and deterministically resolves items against catalog.",
)
async def extract_order_from_message(
    request: OrderIntakeRequest,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    ai_service: AIIntakeService = Depends(get_ai_intake_service),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
) -> OrderIntakeResponse:
    try:
        proposal = await ai_service.extract_and_match_order(
            raw_message=request.message,
            business_id=membership.business_id,
            product_repo=product_repo,
            customer_repo=customer_repo,
        )
        return proposal
    except AIConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AI_NOT_CONFIGURED",
                "message": str(e),
                "action": "Please configure an AI_API_KEY on the server or proceed with manual order entry.",
            },
        ) from e
    except AIExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "AI_EXTRACTION_FAILED",
                "message": str(e),
                "action": "Please refine the customer message or enter order details manually.",
            },
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
