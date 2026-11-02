import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from config import AwgParams


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


def create_client_config(private_key, server_public_key, server_endpoint, client_ip, awg):
    """
    Создание конфигурации клиента для AmneziaWG.

    Args:
        private_key: приватный ключ клиента
        server_public_key: публичный ключ сервера
        server_endpoint: IP:порт сервера (например: 1.2.3.4:51820)
        client_ip: IP адрес клиента в VPN сети (например: 10.0.0.2)
        awg: AwgParams сервера. S1-S4, H1-H4 и HeaderProtectionKey обязаны совпадать
             с конфигом сервера, иначе рукопожатие не пройдёт.

    Returns:
        str: конфигурация в формате AmneziaWG
    """
    interface_lines = [
        f"PrivateKey = {private_key}",
        f"Address = {client_ip}/32",
        "DNS = 1.1.1.1, 8.8.8.8",
        "MTU = 1280",
    ]
    interface_lines += [f"{k} = {v}" for k, v in awg.interface_items()]

    return (
        "[Interface]\n"
        + "\n".join(interface_lines)
        + "\n\n[Peer]\n"
        + f"PublicKey = {server_public_key}\n"
        + f"Endpoint = {server_endpoint}\n"
        + "AllowedIPs = 0.0.0.0/0, ::/0\n"
        + "PersistentKeepalive = 10\n"
    )


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
        awg=AwgParams(),
    )
    print(config)
