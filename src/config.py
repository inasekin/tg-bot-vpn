import os
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, overload

# Параметры обфускации AmneziaWG, которые попадают в секцию [Interface] клиентского
# конфига. Порядок словаря = порядок строк в конфиге.
#
# Server-side (ОБЯЗАНЫ совпадать с awg-конфигом сервера): S1-S4, H1-H4, HeaderProtectionKey.
# Client-side (могут отличаться): Jc, Jmin, Jmax, ContentPaddingAddition и тайминги.
#
# Любой параметр переопределяется per-server переменной WG_SERVER_<ИМЯ>_<KEY>,
# например WG_SERVER_H1_NL=100-200. Пустое значение (WG_SERVER_S3_US=) убирает
# параметр из конфига — нужно для серверов на старой версии AmneziaWG.
AWG_DEFAULTS: Dict[str, str] = {
    "Jc": "5",
    "Jmin": "50",
    "Jmax": "1000",
    "S1": "86",
    "S2": "123",
    "S3": "45",
    "S4": "67",
    "H1": "1234567-1235567",
    "H2": "2345678-2346678",
    "H3": "3456789-3457789",
    "H4": "4567890-4568890",
    # I1-I5 (CPS, AWG 1.5+): пакеты-сигнатуры (мимикрия под QUIC/DNS), которые КЛИЕНТ шлёт
    # перед рукопожатием, чтобы DPI провайдера не опознал AmneziaWG. Только client-side:
    # сервер их не проверяет и совпадать с сервером они не обязаны. Пусто = не отправляются.
    # Синтаксис: <b 0xHEX> <t> <r N> <rc N> <rd N>, N <= 1000. Задаются через .env.
    "I1": "",
    "I2": "",
    "I3": "",
    "I4": "",
    "I5": "",
    # --- Параметры AWG 3.x: по умолчанию ВЫКЛЮЧЕНЫ, включаются через .env осознанно. ---
    # На ноябрь 2026 у модуля ядра (v3.1.20260906) открыты баги совместимости с
    # amneziawg-go (на нём клиенты Windows/Android/iOS):
    #   - HeaderProtectionKey: рукопожатие между kmod и go игнорируется
    #     https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/issues/222
    #   - RandomTrailers: потеря пакетов данных при диапазонных H1-H4 / разных S1-S4
    #     https://github.com/amnezia-vpn/amneziawg-linux-kernel-module/issues/226
    # Рекомендации docs.amnezia.org для 3.1: с HeaderProtectionKey — H1..H4 = 1,2,3,4
    # и S1-S4 >= 12; с RandomTrailers — S1 = S2 = S3 = S4.
    "HeaderProtectionKey": "",  # секрет, только через .env (`awg genkey` на сервере)
    "ContentPaddingAddition": "",
    "RandomTrailers": "",
    "DisableCookies": "",
    "RekeyAfterTime": "",
    "RekeyTimeout": "",
    "RejectAfterTime": "",
    "KeepaliveTimeout": "",
    "MaxHandshakeAttempts": "",
}

_INT_PARAMS = ("Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4")
_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
_CPS_TAG_RE = re.compile(r"<(?:b 0x(?:[0-9a-fA-F]{2})+|t|r \d+|rc \d+|rd \d+)>")


def _env_name(param: str) -> str:
    """HeaderProtectionKey -> HEADER_PROTECTION_KEY, Jmin -> JMIN, H1 -> H1."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", param).upper()


def _parse_range(value: str):
    m = _RANGE_RE.match(value)
    if not m:
        raise ValueError(f"ожидается число или диапазон 'x-y', получено '{value}'")
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) is not None else lo
    if lo > hi:
        raise ValueError(f"в диапазоне '{value}' начало больше конца")
    return lo, hi


def _validate_cps(name: str, value: str) -> None:
    """Проверка синтаксиса CPS-строки I1-I5: только известные теги, N <= 1000."""
    if _CPS_TAG_RE.sub("", value).strip():
        raise ValueError(f"{name}: неизвестные теги или мусор в '{value}'")
    for n in re.findall(r"<(?:r|rc|rd) (\d+)>", value):
        if int(n) > 1000:
            raise ValueError(f"{name}: длина {n} в <r/rc/rd N> больше 1000")


@dataclass
class AwgParams:
    """Параметры обфускации AmneziaWG одного сервера."""

    values: Dict[str, str] = field(default_factory=lambda: dict(AWG_DEFAULTS))

    def interface_items(self):
        """Пары (ключ, значение) для [Interface], пустые значения пропускаются."""
        return [(k, v) for k, v in self.values.items() if v != ""]

    def validate(self, server_key: str = "?") -> None:
        v = {k: val for k, val in self.values.items() if val != ""}
        try:
            for name in ("I1", "I2", "I3", "I4", "I5"):
                if name in v:
                    _validate_cps(name, v[name])

            for name in _INT_PARAMS:
                if name in v and not v[name].isdigit():
                    raise ValueError(f"{name} должен быть целым числом, получено '{v[name]}'")

            for name in ("RandomTrailers", "DisableCookies"):
                if name in v and v[name] not in ("on", "off"):
                    raise ValueError(f"{name} должен быть on/off, получено '{v[name]}'")

            if "Jmin" in v and "Jmax" in v and int(v["Jmin"]) > int(v["Jmax"]):
                raise ValueError("Jmin должен быть <= Jmax")

            h_ranges = []
            for name in ("H1", "H2", "H3", "H4"):
                if name in v:
                    h_ranges.append((name, *_parse_range(v[name])))
            h_ranges.sort(key=lambda r: r[1])
            for prev, cur in zip(h_ranges, h_ranges[1:]):
                if cur[1] <= prev[2]:
                    raise ValueError(f"диапазоны {prev[0]} и {cur[0]} пересекаются")

            if v.get("RandomTrailers") == "on":
                sizes = {v.get(name, "0") for name in ("S1", "S2", "S3", "S4")}
                if len(sizes) != 1:
                    raise ValueError(
                        "RandomTrailers = on требует S1 = S2 = S3 = S4 (docs.amnezia.org, "
                        "kernel-module issue #226), сейчас: "
                        + ", ".join(f"{n}={v.get(n, '<нет>')}" for n in ("S1", "S2", "S3", "S4"))
                    )

            if "HeaderProtectionKey" in v:
                for name in ("S1", "S2", "S3", "S4"):
                    if int(v.get(name, "0")) < 12:
                        raise ValueError(
                            f"HeaderProtectionKey требует S1-S4 >= 12, а {name}={v.get(name, 0)}"
                        )
        except ValueError as e:
            raise ValueError(f"Некорректные AWG-параметры сервера '{server_key}': {e}") from e

    @classmethod
    def from_env(cls, server_key: str) -> "AwgParams":
        values = {
            param: _getenv_for(f"WG_SERVER_{_env_name(param)}", server_key, default).strip()
            for param, default in AWG_DEFAULTS.items()
        }
        params = cls(values)
        params.validate(server_key)
        return params


@dataclass
class ServerConfig:
    """Конфигурация одного VPN-сервера (AmneziaWG)."""

    key: str  # внутренний идентификатор, например "nl" или "us"
    label: str  # человекочитаемое имя для UI, например "🇳🇱 Нидерланды"
    public_key: str  # публичный ключ AmneziaWG сервера
    endpoint: str  # host:port для подключения клиентов
    subnet_prefix: str  # префикс подсети, например "10.0.0." или "10.0.1."
    interface: str = "wg0"  # имя интерфейса AmneziaWG на сервере
    # Если ssh_host пуст — команды выполняются локально (subprocess).
    # Если задан — команды выполняются удалённо через `ssh -i ssh_key_path user@ssh_host`.
    ssh_host: Optional[str] = None
    ssh_user: str = "root"
    ssh_key_path: Optional[str] = None
    awg: AwgParams = field(default_factory=AwgParams)

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


@overload
def _getenv_for(name: str, server_key: str) -> Optional[str]: ...
@overload
def _getenv_for(name: str, server_key: str, default: str) -> str: ...
def _getenv_for(name: str, server_key: str, default: Optional[str] = None) -> Optional[str]:
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
            awg=AwgParams.from_env(server_key),
        )

    return servers


SERVERS = _load_servers()

DEFAULT_SERVER_KEY = next(iter(SERVERS), None)
