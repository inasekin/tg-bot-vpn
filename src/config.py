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


# Исторически нидерландский сервер был заведён под ключом "ru" (и подписан как
# "🇷🇺 Россия", хотя физически стоит в Нидерландах). Здесь ключ "ru" считается
# устаревшим алиасом "nl": старые .env и старые записи в БД продолжают работать.
LEGACY_KEY_ALIASES = {"ru": "nl"}

LABELS = {
    "nl": "🇳🇱 Нидерланды",
    "us": "🇺🇸 США",
}


def _getenv_for(name: str, server_key: str, default=None):
    """
    Читает переменную окружения WG_SERVER_<NAME>_<KEY>, а если её нет —
    пробует устаревшее имя ключа (например, _RU вместо _NL).
    """
    value = os.getenv(f"{name}_{server_key.upper()}")
    if value is None:
        for legacy, actual in LEGACY_KEY_ALIASES.items():
            if actual == server_key:
                value = os.getenv(f"{name}_{legacy.upper()}")
                if value is not None:
                    break
    return default if value is None else value


def _load_servers() -> dict:
    """
    Загружает конфигурацию серверов из переменных окружения.

    Для каждого сервера ожидаются переменные с суффиксом _<KEY> в верхнем регистре, например:
        WG_SERVER_PUBLIC_KEY_NL=...
        WG_SERVER_ENDPOINT_NL=1.2.3.4:51820
        WG_SERVER_SUBNET_NL=10.0.0.
        WG_SERVER_SSH_HOST_NL=        (пусто = локальный сервер, команды выполняются напрямую)

        WG_SERVER_PUBLIC_KEY_US=...
        WG_SERVER_ENDPOINT_US=5.6.7.8:51820
        WG_SERVER_SUBNET_US=10.0.1.
        WG_SERVER_SSH_HOST_US=5.6.7.8
        WG_SERVER_SSH_USER_US=root
        WG_SERVER_SSH_KEY_US=/root/.ssh/bot_us_server

    WG_SERVERS задаёт список ключей серверов через запятую, например: WG_SERVERS=nl,us
    Порядок в WG_SERVERS определяет порядок кнопок в боте.
    """
    servers = {}
    raw_keys = [s.strip() for s in os.getenv("WG_SERVERS", "nl").split(",") if s.strip()]
    server_keys = [LEGACY_KEY_ALIASES.get(k, k) for k in raw_keys]

    for server_key in server_keys:
        public_key = _getenv_for("WG_SERVER_PUBLIC_KEY", server_key)
        endpoint = _getenv_for("WG_SERVER_ENDPOINT", server_key)
        subnet_prefix = _getenv_for("WG_SERVER_SUBNET", server_key, "10.0.0.")
        interface = _getenv_for("WG_SERVER_INTERFACE", server_key, "wg0")
        label = _getenv_for(
            "WG_SERVER_LABEL", server_key, LABELS.get(server_key, server_key.upper())
        )

        ssh_host = _getenv_for("WG_SERVER_SSH_HOST", server_key) or None
        ssh_user = _getenv_for("WG_SERVER_SSH_USER", server_key, "root")
        ssh_key_path = _getenv_for("WG_SERVER_SSH_KEY", server_key) or None

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
