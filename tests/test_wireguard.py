import base64

from config import AWG_DEFAULTS, AwgParams
from wireguard import create_client_config, generate_keys


def _parse(conf: str) -> dict:
    sections, current = {}, None
    for line in conf.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("["):
            current = sections.setdefault(line.strip("[]"), {})
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        assert key not in current, f"дубликат ключа {key}"
        current[key] = value
    return sections


def test_generate_keys_are_32_byte_base64():
    priv, pub = generate_keys()
    assert len(base64.b64decode(priv)) == 32
    assert len(base64.b64decode(pub)) == 32
    assert priv != pub


def test_client_config_contains_server_params():
    awg = AwgParams({**AWG_DEFAULTS, "HeaderProtectionKey": "hpk", "S4": ""})
    conf = _parse(create_client_config("PRIV", "PUB", "1.2.3.4:51820", "10.0.0.7", awg))

    iface, peer = conf["Interface"], conf["Peer"]
    assert iface["PrivateKey"] == "PRIV"
    assert iface["Address"] == "10.0.0.7/32"
    assert iface["H1"] == AWG_DEFAULTS["H1"]
    assert iface["HeaderProtectionKey"] == "hpk"
    assert "S4" not in iface
    assert peer == {
        "PublicKey": "PUB",
        "Endpoint": "1.2.3.4:51820",
        "AllowedIPs": "0.0.0.0/0, ::/0",
        "PersistentKeepalive": "10",
    }


def test_client_config_has_only_known_interface_keys():
    conf = _parse(create_client_config("P", "S", "h:1", "10.0.0.2", AwgParams()))
    allowed = {"PrivateKey", "Address", "DNS", "MTU", *AWG_DEFAULTS}
    assert set(conf["Interface"]) <= allowed
