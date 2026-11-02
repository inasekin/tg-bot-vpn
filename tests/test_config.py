import pytest

import config
from config import AWG_DEFAULTS, AwgParams, _env_name, _load_servers


def test_env_name():
    assert _env_name("HeaderProtectionKey") == "HEADER_PROTECTION_KEY"
    assert _env_name("Jmin") == "JMIN"
    assert _env_name("H1") == "H1"
    assert _env_name("ContentPaddingAddition") == "CONTENT_PADDING_ADDITION"
    assert _env_name("RandomTrailers") == "RANDOM_TRAILERS"


def test_defaults_are_valid():
    AwgParams().validate()


def test_awg3_params_omitted_by_default():
    keys = {k for k, _ in AwgParams().interface_items()}
    assert keys == {"Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4", "H1", "H2", "H3", "H4"}


def test_random_trailers_requires_equal_s():
    AwgParams(
        {**AWG_DEFAULTS, "RandomTrailers": "on", **dict.fromkeys(("S1", "S2", "S3", "S4"), "16")}
    ).validate()
    with pytest.raises(ValueError, match="S1 = S2 = S3 = S4"):
        AwgParams({**AWG_DEFAULTS, "RandomTrailers": "on"}).validate()


@pytest.mark.parametrize(
    "override, message",
    [
        ({"Jmin": "2000"}, "Jmin"),
        ({"S1": "abc"}, "S1"),
        ({"RandomTrailers": "yes"}, "on/off"),
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


QUIC_I1 = "<b 0xc30000000108><r 8><b 0x08><r 8><b 0x004496><r 1000><r 174>"


def test_cps_valid_and_emitted(monkeypatch):
    monkeypatch.setenv("WG_SERVERS", "nl")
    monkeypatch.setenv("WG_SERVER_PUBLIC_KEY_NL", "pub")
    monkeypatch.setenv("WG_SERVER_ENDPOINT_NL", "1.1.1.1:443")
    monkeypatch.setenv("WG_SERVER_I1_NL", QUIC_I1)
    items = dict(_load_servers()["nl"].awg.interface_items())
    assert items["I1"] == QUIC_I1
    assert "I2" not in items


@pytest.mark.parametrize(
    "value, message",
    [
        ("<b 0xabc>", "неизвестные теги"),  # нечётное число hex-символов
        ("<x 5>", "неизвестные теги"),
        ("<r 8> junk", "неизвестные теги"),
        ("<r 1001>", "больше 1000"),
    ],
)
def test_cps_invalid(value, message):
    with pytest.raises(ValueError, match=message):
        AwgParams({**AWG_DEFAULTS, "I1": value}).validate()
