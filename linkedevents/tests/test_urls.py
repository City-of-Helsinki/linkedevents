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
    response = client.get("/docs/schema/")

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
    response = client.get("/docs/swagger-ui/")

    assert response.status_code == 200
    assert "Linked Events information API" in str(response.content)
