import json
import pytest
from services import business_config_service as bcs
from exceptions import ServiceUnavailableError


def test_encrypt_decrypt_roundtrip():
    url = "postgres://u:p@host:5432/db"
    enc = bcs.encrypt_url(url)
    assert enc != url                      # actually encrypted
    assert bcs.decrypt_url(enc) == url     # round-trips


def test_mask_url_hides_credentials():
    enc = bcs.encrypt_url("postgres://user:secret@host:5432/db")
    masked = bcs.mask_url(enc)
    assert "secret" not in masked
    assert masked.startswith("...")


async def test_get_config_or_raise_when_unconfigured(analytics_session):
    with pytest.raises(ServiceUnavailableError):
        await bcs.get_config_or_raise(analytics_session)


async def test_update_config_creates_and_parses(analytics_session):
    # update_config is now pure persistence — no pool side effect, no patching needed.
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
        new_db_url="postgres://u:p@host:5432/db",
    )
    parsed = bcs.get_parsed_config(config)
    assert parsed["business_name"] == "Acme"
    assert parsed["explain_cost_threshold"] == 12345
    assert parsed["business_rules"] == [{"rule": "r1"}]
    assert "secret" not in parsed["db_url_masked"]
