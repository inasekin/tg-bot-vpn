import sqlite3

import pytest

from database import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "bot.db"))


def test_next_ip_per_server(db):
    assert db.get_next_ip("nl", "10.0.0.") == "10.0.0.2"
    db.add_vpn_config(1, "a", "priv", "pub", "10.0.0.2", "nl")
    assert db.get_next_ip("nl", "10.0.0.") == "10.0.0.3"
    assert db.get_next_ip("us", "10.0.1.") == "10.0.1.2"


def test_next_ip_exhausted(db):
    db.add_vpn_config(1, "a", "priv", "pub", "10.0.0.254", "nl")
    with pytest.raises(Exception, match="закончились"):
        db.get_next_ip("nl", "10.0.0.")


def test_migration_renames_ru_to_nl(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE vpn_configs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, "
        "name TEXT NOT NULL, private_key TEXT NOT NULL, public_key TEXT NOT NULL, "
        "ip_address TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO vpn_configs (user_id, name, private_key, public_key, ip_address) "
        "VALUES (1, 'old', 'p', 'q', '10.0.0.5')"
    )
    conn.commit()
    conn.close()

    db = Database(str(path))

    [cfg] = db.get_all_vpn_configs(1)
    assert cfg["server"] == "nl"
    assert db.get_next_ip("nl", "10.0.0.") == "10.0.0.6"
