import pytest
from services import business_config_service as bcs
from services import crypto
from api.schemas.admin import BusinessConfigOut
from exceptions import ServiceUnavailableError


def test_crypto_roundtrip():
    secret = "postgres://u:p@host:5432/db"
    enc = crypto.encrypt(secret)
    assert enc != secret           # actually encrypted
    assert crypto.decrypt(enc) == secret


def test_mask_hides_credentials():
    enc = crypto.encrypt("postgres://user:supersecret@host:5432/db")
    masked = crypto.mask(enc)
    assert "supersecret" not in masked


async def test_get_config_or_raise_when_unconfigured(analytics_session):
    with pytest.raises(ServiceUnavailableError):
        await bcs.get_config_or_raise(analytics_session)


async def test_update_config_persists_and_serializes(analytics_session):
    # update_config is pure persistence; the schema owns the model→DTO shaping.
    config = await bcs.update_config(
        analytics_session,
        data={
            "business_name": "Acme",
            "business_description": "desc",
            "domain_context": "ctx",
            "business_rules": [{"rule": "r1"}],
            "table_descriptions": {"t": "d"},
            "kpi_definitions": [{"name": "GMV", "sql": "SELECT 1", "format": "number", "icon": "x"}],
            "starter_questions": ["q1"],
            "explain_cost_threshold": 12345,
        },
        new_db_url="postgres://u:secret@host:5432/db",
    )
    out = BusinessConfigOut.from_model(config)
    assert out.business_name == "Acme"
    assert out.explain_cost_threshold == 12345
    assert out.business_rules == [{"rule": "r1"}]
    assert out.db_url == "postgres://u:secret@host:5432/db"  # full URL returned to superuser
