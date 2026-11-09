"""Check how the REST API selects locally registered norm versions."""

from fastapi.testclient import TestClient

from judicial_intelligence.api import create_app


def test_norm_versions_respect_inclusive_dates_and_gaps(tmp_path):
    norm_id = "SYNTHETIC:1"
    headers = {"X-API-Key": "test-key"}
    with TestClient(create_app(str(tmp_path / "norms.db"), api_key="test-key")) as client:
        def register(text, start, end=None):
            response = client.post(
                "/v1/norms",
                headers=headers,
                json={
                    "norm_id": norm_id,
                    "text": text,
                    "valid_from": start,
                    "valid_to": end,
                    "source_url": "https://example.org/synthetic",
                },
            )
            assert response.status_code == 201, response.text
            return response.json()["id"]

        later = register("Later version", "2025-02-01")
        earlier = register("Earlier version", "2025-01-01", "2025-01-15")

        for day, expected_ids in [
            ("2024-12-31", []),
            ("2025-01-01", [earlier]),
            ("2025-01-15", [earlier]),
            ("2025-01-16", []),
            ("2025-02-01", [later]),
            ("2026-01-01", [later]),
        ]:
            response = client.get(
                "/v1/norms", headers=headers, params={"norm_id": norm_id, "on_date": day}
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert [version["id"] for version in result["versions"]] == expected_ids, day
            assert result["source_verification"] == "unverified"
            assert all(
                version["verification_status"] == "unverified_user_input"
                for version in result["versions"]
            ), day
