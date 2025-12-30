import yaml
from drf_spectacular.validation import validate_schema

from linkedevents import __version__


def test_healthz(client):
    response = client.get("/healthz")

    assert response.status_code == 200


def test_readiness(client, settings):
    response = client.get("/readiness")

    data = response.json()
    assert response.status_code == 200
    assert len(data) == 4
    assert data["status"] == "ok"
    assert data["packageVersion"] == __version__
    assert data["commitHash"] == settings.COMMIT_HASH
    assert "buildTime" in data


def test_openapi_schema(client):
    response = client.get("/api-docs/schema/")

    assert response.status_code == 200
    assert response.content.startswith(b"openapi: 3.0.3\n")
    assert response.accepted_media_type == "application/vnd.oai.openapi"
    assert response.headers["CONTENT-DISPOSITION"] == (
        'inline; filename="Linked Events information API (v1).yaml"'
    )

    schema = yaml.load(response.content, Loader=yaml.SafeLoader)
    validate_schema(schema)
    # Number of the API endpoints that are supposed to be covered by the schema.
    assert len(schema["paths"]) == 38


def test_swagger_ui(client):
    response = client.get("/api-docs/swagger-ui/")

    assert response.status_code == 200
    assert "Linked Events information API" in str(response.content)


def test_redoc(client):
    response = client.get("/api-docs/")

    assert response.status_code == 200


def test_root_redirects_to_v1(client):
    """Test that root path redirects to /v1/"""
    response = client.get("/", follow=False)

    assert response.status_code == 302
    assert response["Location"] == "/v1/"


def test_root_redirect_follows_to_v1_redoc(client):
    """Test that following root redirect leads to v1 ReDoc"""
    response = client.get("/", follow=True)

    assert response.status_code == 200
    # Check that we ended up at the ReDoc page
    assert "redoc" in str(response.content).lower()


def test_v1_redoc(client):
    """Test that /v1/ serves ReDoc documentation"""
    response = client.get("/v1/")

    assert response.status_code == 200
    assert "redoc" in str(response.content).lower()


def test_v1_schema(client):
    """Test that /v1/schema/ serves OpenAPI schema"""
    response = client.get("/v1/schema/")

    assert response.status_code == 200
    assert response.content.startswith(b"openapi: 3.0.3\n")
    assert response.accepted_media_type == "application/vnd.oai.openapi"

    schema = yaml.load(response.content, Loader=yaml.SafeLoader)
    validate_schema(schema)


def test_v1_swagger_ui(client):
    """Test that /v1/swagger-ui/ serves Swagger UI"""
    response = client.get("/v1/swagger-ui/")

    assert response.status_code == 200
    assert "Linked Events information API" in str(response.content)


def test_legacy_docs_schema_redirect(client):
    """Test that /docs/schema/ redirects to /api-docs/schema/"""
    response = client.get("/docs/schema/", follow=False)

    assert response.status_code == 301
    assert response["Location"] == "/api-docs/schema/"


def test_legacy_docs_swagger_ui_redirect(client):
    """Test that /docs/swagger-ui/ redirects to /api-docs/swagger-ui/"""
    response = client.get("/docs/swagger-ui/", follow=False)

    assert response.status_code == 301
    assert response["Location"] == "/api-docs/swagger-ui/"


def test_legacy_docs_schema_redirect_follows(client):
    """Test that following /docs/schema/ redirect leads to schema"""
    response = client.get("/docs/schema/", follow=True)

    assert response.status_code == 200
    assert response.content.startswith(b"openapi: 3.0.3\n")


def test_legacy_docs_swagger_ui_redirect_follows(client):
    """Test that following /docs/swagger-ui/ redirect leads to Swagger UI"""
    response = client.get("/docs/swagger-ui/", follow=True)

    assert response.status_code == 200
    assert "Linked Events information API" in str(response.content)
