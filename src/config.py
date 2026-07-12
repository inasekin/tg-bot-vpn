import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    """Конфигурация одного VPN-сервера (AmneziaWG)."""

    key: str  # внутренний идентификатор, например "ru" или "us"
    label: str  # человекочитаемое имя для UI, например "🇷🇺 Россия"
    public_key: str  # публичный ключ AmneziaWG сервера
    endpoint: str  # host:port для подключения клиентов
    subnet_prefix: str  # префикс подсети, например "10.0.0." или "10.0.1."
    interface: str = "wg0"  # имя интерфейса AmneziaWG на сервере
    # Если ssh_host пуст — команды выполняются локально (subprocess).
    # Если задан — команды выполняются удалённо через `ssh -i ssh_key_path user@ssh_host`.
    ssh_host: Optional[str] = None
    ssh_user: str = "root"
    ssh_key_path: Optional[str] = None

    @property
    def is_remote(self) -> bool:
        return bool(self.ssh_host)


def _load_servers() -> dict:
    """
    Загружает конфигурацию серверов из переменных окружения.

    Для каждого сервера ожидаются переменные с суффиксом _<KEY> в верхнем регистре, например:
        WG_SERVER_PUBLIC_KEY_RU=...
        WG_SERVER_ENDPOINT_RU=1.2.3.4:51820
        WG_SERVER_SUBNET_RU=10.0.0.
        WG_SERVER_SSH_HOST_RU=        (пусто = локальный сервер, команды выполняются напрямую)

        WG_SERVER_PUBLIC_KEY_US=...
        WG_SERVER_ENDPOINT_US=5.6.7.8:51820
        WG_SERVER_SUBNET_US=10.0.1.
        WG_SERVER_SSH_HOST_US=5.6.7.8
        WG_SERVER_SSH_USER_US=root
        WG_SERVER_SSH_KEY_US=/root/.ssh/bot_us_server

    WG_SERVERS задаёт список ключей серверов через запятую, например: WG_SERVERS=ru,us
    Порядок в WG_SERVERS определяет порядок кнопок в боте.
    """
    servers = {}
    server_keys = [s.strip() for s in os.getenv("WG_SERVERS", "ru").split(",") if s.strip()]

    labels = {
        "ru": "🇷🇺 Россия",
        "us": "🇺🇸 США",
    }

    for server_key in server_keys:
        suffix = server_key.upper()

        public_key = os.getenv(f"WG_SERVER_PUBLIC_KEY_{suffix}")
        endpoint = os.getenv(f"WG_SERVER_ENDPOINT_{suffix}")
        subnet_prefix = os.getenv(f"WG_SERVER_SUBNET_{suffix}", "10.0.0.")
        interface = os.getenv(f"WG_SERVER_INTERFACE_{suffix}", "wg0")
        label = os.getenv(f"WG_SERVER_LABEL_{suffix}", labels.get(server_key, server_key.upper()))

        ssh_host = os.getenv(f"WG_SERVER_SSH_HOST_{suffix}") or None
        ssh_user = os.getenv(f"WG_SERVER_SSH_USER_{suffix}", "root")
        ssh_key_path = os.getenv(f"WG_SERVER_SSH_KEY_{suffix}") or None

        if not public_key or not endpoint:
            continue

        servers[server_key] = ServerConfig(
            key=server_key,
            label=label,
            public_key=public_key,
            endpoint=endpoint,
            subnet_prefix=subnet_prefix,
            interface=interface,
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_key_path=ssh_key_path,
        )

    return servers


SERVERS = _load_servers()

DEFAULT_SERVER_KEY = next(iter(SERVERS), None)
