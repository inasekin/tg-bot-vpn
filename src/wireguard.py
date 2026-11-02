import base64
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization


def generate_keys():
    """
    Генерация пары ключей AmneziaWG (приватный, публичный)

    Returns:
        tuple: (private_key, public_key)
    """
    private_key_obj = X25519PrivateKey.generate()

    private_bytes = private_key_obj.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key = base64.b64encode(private_bytes).decode("utf-8")

    public_key_obj = private_key_obj.public_key()
    public_bytes = public_key_obj.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    public_key = base64.b64encode(public_bytes).decode("utf-8")

    return private_key, public_key

def create_client_config(private_key, server_public_key, server_endpoint, client_ip):
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/32
DNS = 1.1.1.1, 8.8.8.8
MTU = 1280
Jc = 5
Jmin = 50
Jmax = 1000
S1 = 86
S2 = 123
S3 = 45
S4 = 67
H1 = 1234567-1235567
H2 = 2345678-2346678
H3 = 3456789-3457789
H4 = 4567890-4568890
HeaderProtectionKey = 8f3a2b1c9d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789ab
ContentPaddingAddition = 20-80
RandomTrailers = on
DisableCookies = off
RekeyAfterTime = 100-120
RekeyTimeout = 3-7
RejectAfterTime = 150-180
KeepaliveTimeout = 5-15
MaxHandshakeAttempts = 15-20

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 10
"""
    return config

if __name__ == "__main__":
    print("Генерация ключей...")
    priv, pub = generate_keys()
    print(f"Private: {priv}")
    print(f"Public: {pub}")

    print("\nТестовая конфигурация:")
    config = create_client_config(
        private_key=priv,
        server_public_key="SERVER_PUBLIC_KEY_HERE",
        server_endpoint="1.2.3.4:51820",
        client_ip="10.0.0.2",
    )
    print(config)
