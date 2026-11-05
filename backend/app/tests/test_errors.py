"""Tests for standardized and safe error responses."""

from fastapi.testclient import TestClient


def test_404_not_found_structure(client: TestClient):
    """Test 404 response returns standard safe envelope."""
    response = client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
    assert "Not Found" in data["error"]["message"]
    assert data["error"]["details"] is None


def test_no_stack_trace_leakage(client: TestClient):
    """Test response text does not leak internal traceback or server file paths."""
    response = client.get("/invalid-path-for-testing")
    assert response.status_code == 404
    body = response.text
    assert "Traceback" not in body
    assert "File \"" not in body


def test_structured_dict_http_exception(client: TestClient):
    """Verify HTTPException with dict details outputs structured code and message."""
    from fastapi import HTTPException

    @client.app.get("/test-structured-error")
    def _endpoint():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CUSTOM_SERVICE_UNAVAILABLE",
                "message": "Custom service error explanation",
                "action": "Retry later",
            },
        )

    response = client.get("/test-structured-error")
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "CUSTOM_SERVICE_UNAVAILABLE"
    assert data["error"]["message"] == "Custom service error explanation"
    assert data["error"]["details"] == {"action": "Retry later"}

