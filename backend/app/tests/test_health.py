"""Tests for health probe endpoints and system status reporting."""

from fastapi.testclient import TestClient


def test_root_health_endpoint(client: TestClient):
    """Test GET /health returns 200 and accurate system status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["app_name"] == "Orqestra API Test"
    assert data["environment"] == "test"
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0

    # Verify component honesty: operational vs not_connected
    components = data["components"]
    assert components["python_runtime"]["status"] == "operational"
    assert components["fastapi_server"]["status"] == "operational"
    assert components["database"]["status"] == "not_connected"
    assert components["ai_service"]["status"] == "not_configured"
    assert components["authentication"]["status"] == "not_connected"


def test_api_v1_health_endpoint(client: TestClient):
    """Test GET /api/v1/health returns 200 and matches root health contract."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "components" in data
    assert data["components"]["database"]["status"] == "not_connected"


def test_openapi_documentation_accessible(client: TestClient):
    """Test development OpenAPI schema is accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Orqestra API Test"
    assert "/health" in schema["paths"]
    assert "/api/v1/health" in schema["paths"]


def test_cors_headers(client: TestClient):
    """Test CORS preflight handling for allowed origins."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
