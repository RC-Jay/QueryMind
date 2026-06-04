from db.safety import validate_sql


def test_allows_plain_select():
    assert validate_sql("SELECT * FROM order_order").ok


def test_allows_subquery_select():
    assert validate_sql("SELECT id FROM (SELECT id FROM users) AS s").ok


def test_blocks_drop():
    r = validate_sql("DROP TABLE users")
    assert not r.ok and "DROP" in r.reason


def test_blocks_delete():
    assert not validate_sql("DELETE FROM order_order").ok


def test_blocks_stacked_statement():
    assert not validate_sql("SELECT 1; DROP TABLE users").ok


def test_blocks_event_tables():
    r = validate_sql("SELECT * FROM order_order_event")
    assert not r.ok and "audit" in r.reason.lower()


def test_blocks_insert_update():
    assert not validate_sql("INSERT INTO t VALUES (1)").ok
    assert not validate_sql("UPDATE t SET x = 1").ok
