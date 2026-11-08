"""Guard against accidental unauthenticated /v1 endpoints.

This checks FastAPI's registered dependency graph, not only decorator text.
"""
from fastapi.routing import APIRoute
from judicial_intelligence.api import create_app


def test_all_v1_routes_require_auth_dependency(tmp_path):
    app = create_app(str(tmp_path / "auth.sqlite3"), api_key="synthetic-key")
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    protected = [route for route in routes if route.path.startswith("/v1/")]
    assert protected, "Expected at least one versioned API endpoint"
    for route in protected:
        dependency_names = {item.call.__name__ for item in route.dependant.dependencies}
        assert "authenticate" in dependency_names, (route.path, sorted(route.methods))


def test_health_is_public_but_versioned_api_is_not(tmp_path):
    from fastapi.testclient import TestClient
    client = TestClient(create_app(str(tmp_path / "auth2.sqlite3"), api_key="synthetic-key"))
    assert client.get("/health").status_code == 200
    assert client.get("/v1/cases").status_code == 401
    assert client.get("/v1/cases", headers={"X-API-Key": "wrong"}).status_code == 401
