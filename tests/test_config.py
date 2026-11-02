import pytest

import config
from config import AWG_DEFAULTS, AwgParams, _env_name, _load_servers


def test_env_name():
    assert _env_name("HeaderProtectionKey") == "HEADER_PROTECTION_KEY"
    assert _env_name("Jmin") == "JMIN"
    assert _env_name("H1") == "H1"
    assert _env_name("ContentPaddingAddition") == "CONTENT_PADDING_ADDITION"


def test_defaults_are_valid():
    AwgParams().validate()


def test_header_protection_key_omitted_by_default():
    keys = [k for k, _ in AwgParams().interface_items()]
    assert "HeaderProtectionKey" not in keys


@pytest.mark.parametrize(
    "override, message",
    [
        ({"Jmin": "2000"}, "Jmin"),
        ({"S1": "abc"}, "S1"),
        ({"H2": "1234000-1234600"}, "пересекаются"),
        ({"H1": "200-100"}, "начало больше конца"),
        ({"HeaderProtectionKey": "key", "S3": "5"}, "S1-S4 >= 12"),
    ],
)
def test_validate_rejects(override, message):
    params = AwgParams({**AWG_DEFAULTS, **override})
    with pytest.raises(ValueError, match=message):
        params.validate("nl")


def test_load_servers_reads_awg_overrides(monkeypatch):
    monkeypatch.setenv("WG_SERVERS", "nl,us")
    monkeypatch.setenv("WG_SERVER_PUBLIC_KEY_NL", "pubnl")
    monkeypatch.setenv("WG_SERVER_ENDPOINT_NL", "1.1.1.1:51820")
    monkeypatch.setenv("WG_SERVER_HEADER_PROTECTION_KEY_NL", "secret")
    monkeypatch.setenv("WG_SERVER_PUBLIC_KEY_US", "pubus")
    monkeypatch.setenv("WG_SERVER_ENDPOINT_US", "2.2.2.2:51820")
    monkeypatch.setenv("WG_SERVER_S3_US", "")
    monkeypatch.setenv("WG_SERVER_H1_US", "1")

    servers = _load_servers()

    assert list(servers) == ["nl", "us"]
    assert servers["nl"].awg.values["HeaderProtectionKey"] == "secret"
    us = dict(servers["us"].awg.interface_items())
    assert "S3" not in us
    assert us["H1"] == "1"


def test_legacy_ru_alias(monkeypatch):
    monkeypatch.setenv("WG_SERVERS", "ru")
    monkeypatch.setenv("WG_SERVER_PUBLIC_KEY_RU", "pub")
    monkeypatch.setenv("WG_SERVER_ENDPOINT_RU", "1.1.1.1:51820")
    monkeypatch.setenv("WG_SERVER_H1_RU", "42")

    servers = _load_servers()

    assert list(servers) == ["nl"]
    assert servers["nl"].label == config.LABELS["nl"]
    assert servers["nl"].awg.values["H1"] == "42"


def test_invalid_awg_env_fails_fast(monkeypatch):
    monkeypatch.setenv("WG_SERVERS", "nl")
    monkeypatch.setenv("WG_SERVER_PUBLIC_KEY_NL", "pub")
    monkeypatch.setenv("WG_SERVER_ENDPOINT_NL", "1.1.1.1:51820")
    monkeypatch.setenv("WG_SERVER_JMIN_NL", "5000")

    with pytest.raises(ValueError, match="'nl'"):
        _load_servers()
