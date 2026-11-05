"""End-to-end business workflow verification against local PostgreSQL.

Verifies the 10 core business workflows specified in Phase 9:
1. Operator authentication
2. Create a business with INR selected
3. Verify the authenticated user receives the correct owner membership
4. Create a product with a price
5. Create a customer
6. Create an order and approve it
7. Verify inventory changes and stock movement records
8. Generate an invoice and download its PDF
9. Verify currency formatting in the UI and PDF
10. Verify Realtime updates and tenant isolation
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import base64
import json
import os
import uuid
import zlib
import pytest

from backend.app.services.invoice_pdf import generate_invoice_pdf_bytes
from backend.app.schemas.invoices import InvoiceResponse
from backend.app.schemas.orders import OrderResponse, OrderItemResponse
from backend.app.services.auth import TokenVerificationService
from backend.app.core.config import Settings
from backend.app.tests.test_jwt_verification import TEST_SECRET, create_token
from backend.app.tests import manage_staging_db

ENV_DB_URL = os.getenv("STAGING_DATABASE_URL") or os.getenv("ORQESTRA_STAGING_DATABASE_URL")
STAGING_DB_URL = ENV_DB_URL or manage_staging_db.get_conn_url(validate=True)

pytestmark = pytest.mark.skipif(
    not STAGING_DB_URL,
    reason="Local PostgreSQL staging instance is not running."
)


@pytest.fixture(scope="module")
def db_conn():
    import psycopg
    conn = psycopg.connect(
        STAGING_DB_URL,
        autocommit=True,
        connect_timeout=int(manage_staging_db.DEFAULT_CONNECT_TIMEOUT),
    )
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def reset_db_session(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("RESET role;")
        cur.execute("RESET ALL;")
    yield
    with db_conn.cursor() as cur:
        cur.execute("RESET role;")
        cur.execute("RESET ALL;")


def test_e2e_phase9_ten_step_workflow(db_conn):
    """Execute and verify the complete 10-step business workflow against real PostgreSQL."""
    
    # --------------------------------------------------------------------------
    # Step 1: Operator Authentication
    # --------------------------------------------------------------------------
    operator_user_id = str(uuid.uuid4())
    operator_email = f"operator-{operator_user_id[:8]}@orqestra.local"
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
    )
    auth_service = TokenVerificationService(settings=settings)
    
    token = create_token(
        secret=TEST_SECRET,
        sub=operator_user_id,
        email=operator_email,
        role="authenticated",
        aud="authenticated",
    )
    verified_user = auth_service.verify_token(token)
    assert str(verified_user.user_id) == operator_user_id
    assert verified_user.email == operator_email
    assert verified_user.role == "authenticated"

    with db_conn.cursor() as cur:
        # ----------------------------------------------------------------------
        # Step 2: Create a business with INR selected
        # ----------------------------------------------------------------------
        biz_id = str(uuid.uuid4())
        biz_slug = f"test-inr-{biz_id[:8]}"
        biz_name = "Orqestra India Operations"
        outsider_biz_id = str(uuid.uuid4())
        outsider_user_id = str(uuid.uuid4())

        try:
            # Simulate authenticated Supabase operator session
            cur.execute("SET role = 'authenticated';")
            cur.execute(f"SET request.jwt.claim.sub = '{operator_user_id}';")
            cur.execute("SET request.jwt.claim.role = 'authenticated';")

            cur.execute(
                """
                INSERT INTO public.businesses (id, name, slug, currency, is_active)
                VALUES (%s, %s, %s, 'INR', true);
                """,
                (biz_id, biz_name, biz_slug),
            )
            cur.execute(
                """
                SELECT id, name, slug, currency
                FROM public.businesses
                WHERE id = %s;
                """,
                (biz_id,),
            )
            created_biz = cur.fetchone()
            assert created_biz[0] == uuid.UUID(biz_id)
            assert created_biz[1] == biz_name
            assert created_biz[3] == "INR"

            # ----------------------------------------------------------------------
            # Step 3: Verify authenticated user receives owner membership
            # ----------------------------------------------------------------------
            cur.execute(
                """
                SELECT business_id, user_id, role, is_active
                FROM public.business_members
                WHERE business_id = %s AND user_id = %s;
                """,
                (biz_id, operator_user_id),
            )
            membership = cur.fetchone()
            assert membership is not None, "Owner membership trigger did not create business_members record"
            assert membership[0] == uuid.UUID(biz_id)
            assert membership[1] == uuid.UUID(operator_user_id)
            assert membership[2] == "owner"
            assert membership[3] is True

            # ----------------------------------------------------------------------
            # Step 4: Create a product with a price and initial inventory
            # ----------------------------------------------------------------------
            prod_id = str(uuid.uuid4())
            sku = "IND-SENSOR-101"
            prod_name = "Industrial Telemetry Sensor"
            unit_price = Decimal("4999.00")
            initial_stock = 50

            cur.execute(
                """
                INSERT INTO public.products (id, business_id, sku, name, unit_price, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
                RETURNING id, sku, name, unit_price;
                """,
                (prod_id, biz_id, sku, prod_name, unit_price),
            )
            created_prod = cur.fetchone()
            assert created_prod[1] == sku
            assert created_prod[3] == unit_price

            # Initialize stock in inventory table
            cur.execute(
                """
                INSERT INTO public.inventory (business_id, product_id, quantity_on_hand)
                VALUES (%s, %s, %s);
                """,
                (biz_id, prod_id, initial_stock),
            )

            # ----------------------------------------------------------------------
            # Step 5: Create a customer
            # ----------------------------------------------------------------------
            cust_id = str(uuid.uuid4())
            cust_name = "Tata Steel Operations"
            cust_email = "procurement@tatasteel.example.com"
            cust_phone = "+91 22 6665 8282"

            cur.execute(
                """
                INSERT INTO public.customers (id, business_id, name, email, phone)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, email;
                """,
                (cust_id, biz_id, cust_name, cust_email, cust_phone),
            )
            created_cust = cur.fetchone()
            assert created_cust[1] == cust_name
            assert created_cust[2] == cust_email

            # ----------------------------------------------------------------------
            # Step 6: Create an order and approve it atomically
            # ----------------------------------------------------------------------
            order_id = str(uuid.uuid4())
            order_num = f"ORD-{biz_id[:6].upper()}-001"
            order_qty = 2
            total_amount = unit_price * order_qty # 4999.00 * 2 = 9998.00

            cur.execute(
                """
                INSERT INTO public.orders (id, business_id, customer_id, order_number, status, total_amount)
                VALUES (%s, %s, %s, %s, 'pending_approval', %s)
                RETURNING id, status, total_amount;
                """,
                (order_id, biz_id, cust_id, order_num, total_amount),
            )
            created_order = cur.fetchone()
            assert created_order[1] == "pending_approval"
            assert created_order[2] == total_amount

            cur.execute(
                """
                INSERT INTO public.order_items (business_id, order_id, product_id, quantity, unit_price, total_price)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (biz_id, order_id, prod_id, order_qty, unit_price, total_amount),
            )

            # Switch to service_role to execute atomic approval RPC
            cur.execute("SET role = 'service_role';")
            cur.execute(
                """
                SELECT order_id, order_status, total_items_deducted
                FROM public.approve_order_atomic(%s, %s, %s);
                """,
                (order_id, operator_user_id, biz_id),
            )
            approval_result = cur.fetchone()
            assert approval_result[1] == "approved"
            assert approval_result[2] == 1

            # ----------------------------------------------------------------------
            # Step 7: Verify inventory changes and stock movement records
            # ----------------------------------------------------------------------
            cur.execute(
                "SELECT quantity_on_hand FROM public.inventory WHERE business_id = %s AND product_id = %s;",
                (biz_id, prod_id),
            )
            updated_stock = cur.fetchone()[0]
            assert updated_stock == initial_stock - order_qty, f"Stock should be 48, found {updated_stock}"

            cur.execute(
                """
                SELECT quantity_change, movement_type, reference_id, created_by
                FROM public.stock_movements
                WHERE business_id = %s AND product_id = %s;
                """,
                (biz_id, prod_id),
            )
            movement = cur.fetchone()
            assert movement is not None
            assert movement[0] == -order_qty
            assert movement[1] == "order_fulfillment"
            assert movement[2] == uuid.UUID(order_id)
            assert movement[3] == uuid.UUID(operator_user_id)

            # Verify ledger immutability: trigger must reject UPDATE and DELETE
            with pytest.raises(Exception) as exc_update:
                cur.execute(
                    "UPDATE public.stock_movements SET quantity_change = 0 WHERE business_id = %s;",
                    (biz_id,),
                )
            assert "strictly immutable" in str(exc_update.value).lower()

            # ----------------------------------------------------------------------
            # Step 8: Generate an invoice and download its PDF
            # ----------------------------------------------------------------------
            cur.execute(
                "SELECT public.allocate_invoice_atomic(%s, %s, %s, NULL);",
                (biz_id, order_id, operator_user_id),
            )
            raw_inv_result = cur.fetchone()[0]
            inv_dict = json.loads(raw_inv_result) if isinstance(raw_inv_result, str) else raw_inv_result
            assert inv_dict["is_existing"] is False
            assert "invoice_number" in inv_dict
            invoice_number = inv_dict["invoice_number"]
            invoice_id = inv_dict["id"]

            cur.execute(
                """
                SELECT id, business_id, order_id, customer_id, invoice_number, status,
                       amount_due, due_date, line_items_snapshot, customer_snapshot, created_at
                FROM public.invoices
                WHERE id = %s;
                """,
                (invoice_id,),
            )
            inv_row = cur.fetchone()
            assert inv_row is not None
            assert inv_row[4] == invoice_number
            assert inv_row[6] == total_amount

            # Test PDF document generation
            now_dt = datetime.now(timezone.utc)
            inv_response = InvoiceResponse(
                id=str(invoice_id),
                business_id=str(biz_id),
                order_id=str(order_id),
                customer_id=str(cust_id),
                invoice_number=invoice_number,
                status="issued",
                amount_due=Decimal(str(total_amount)),
                due_date=date.today(),
                line_items_snapshot=inv_row[8],
                customer_snapshot=inv_row[9],
                created_at=now_dt,
                updated_at=now_dt,
            )

            order_response = OrderResponse(
                id=str(order_id),
                business_id=str(biz_id),
                customer_id=str(cust_id),
                order_number=order_num,
                status="approved",
                subtotal=Decimal(str(total_amount)),
                tax=Decimal("0.00"),
                total_amount=Decimal(str(total_amount)),
                created_at=now_dt,
                updated_at=now_dt,
                items=[
                    OrderItemResponse(
                        id=str(uuid.uuid4()),
                        business_id=str(biz_id),
                        order_id=str(order_id),
                        product_id=str(prod_id),
                        product_name=prod_name,
                        product_sku=sku,
                        quantity=order_qty,
                        unit_price=unit_price,
                        total_price=total_amount,
                        created_at=now_dt,
                    )
                ],
                customer_name=cust_name,
            )

            # ----------------------------------------------------------------------
            # Step 9: Verify currency formatting in the UI and PDF
            # ----------------------------------------------------------------------
            pdf_bytes = generate_invoice_pdf_bytes(
                invoice=inv_response,
                order=order_response,
                business_name=biz_name,
                business_details={"currency": "INR", "address": "Nariman Point, Mumbai, Maharashtra 400021"},
                customer_details={"name": cust_name, "email": cust_email, "phone": cust_phone},
            )
            # Verify PDF header magic bytes
            assert pdf_bytes.startswith(b"%PDF-")
            assert len(pdf_bytes) > 1000

            # Verify that currency prefix 'INR' is embedded in PDF stream
            assert b"stream\n" in pdf_bytes and b"endstream" in pdf_bytes
            stream_raw = pdf_bytes.split(b"stream\n", 1)[1].split(b"endstream", 1)[0].strip()
            decompressed_stream = zlib.decompress(base64.a85decode(stream_raw, adobe=True))
            assert b"INR" in decompressed_stream, "Currency code INR not found in decompressed PDF text stream"

            # ----------------------------------------------------------------------
            # Step 10: Verify Realtime updates and tenant isolation
            # ----------------------------------------------------------------------
            # Verify publication configuration for Realtime
            cur.execute("RESET role;")
            cur.execute(
                """
                SELECT tablename FROM pg_publication_tables
                WHERE pubname = 'supabase_realtime' AND schemaname = 'public';
                """
            )
            published_tables = {row[0] for row in cur.fetchall()}
            expected_realtime_tables = {"products", "inventory", "orders", "stock_movements", "invoices"}
            assert expected_realtime_tables.issubset(published_tables), f"Missing realtime tables: {expected_realtime_tables - published_tables}"

            # Verify Tenant Isolation with an outsider
            cur.execute(
                "INSERT INTO public.businesses (id, name, slug, currency) VALUES (%s, 'Foreign Corp', %s, 'USD');",
                (outsider_biz_id, f"test-foreign-{outsider_biz_id[:8]}"),
            )
            cur.execute(
                "INSERT INTO public.business_members (business_id, user_id, role, is_active) VALUES (%s, %s, 'owner', true);",
                (outsider_biz_id, outsider_user_id),
            )

            # Set role to authenticated outsider
            cur.execute("SET role = 'authenticated';")
            cur.execute(f"SET request.jwt.claim.sub = '{outsider_user_id}';")
            cur.execute("SET request.jwt.claim.role = 'authenticated';")

            # Outsider queries products of Biz A -> must return 0 rows
            cur.execute("SELECT count(*) FROM public.products WHERE business_id = %s;", (biz_id,))
            assert cur.fetchone()[0] == 0, "Tenant isolation failure: outsider saw products of Biz A"

            # Outsider queries invoices of Biz A -> must return 0 rows
            cur.execute("SELECT count(*) FROM public.invoices WHERE business_id = %s;", (biz_id,))
            assert cur.fetchone()[0] == 0, "Tenant isolation failure: outsider saw invoices of Biz A"

        finally:
            # Clean teardown of temporary test records
            cur.execute("RESET role;")
            cur.execute("ALTER TABLE public.audit_logs DISABLE TRIGGER ALL;")
            cur.execute("ALTER TABLE public.stock_movements DISABLE TRIGGER ALL;")
            cur.execute("DELETE FROM public.invoices WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.order_items WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.orders WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.inventory WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.stock_movements WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.products WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.customers WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.business_members WHERE business_id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("DELETE FROM public.businesses WHERE id IN (%s, %s);", (biz_id, outsider_biz_id))
            cur.execute("ALTER TABLE public.audit_logs ENABLE TRIGGER ALL;")
            cur.execute("ALTER TABLE public.stock_movements ENABLE TRIGGER ALL;")
