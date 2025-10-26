import base64
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization


def generate_keys():
    """
    Генерация пары ключей WireGuard (приватный, публичный)

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
    """
    Создание конфигурации клиента

    Args:
        private_key: Приватный ключ клиента
        server_public_key: Публичный ключ сервера
        server_endpoint: IP:порт сервера (например: 1.2.3.4:51820)
        client_ip: IP адрес клиента в VPN сети (например: 10.0.0.2)

    Returns:
        str: Конфигурация в формате WireGuard
    """
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/32
DNS = 1.1.1.1, 8.8.8.8
MTU = 1380

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
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
