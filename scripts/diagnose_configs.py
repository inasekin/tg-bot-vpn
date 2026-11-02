"""
Диагностика VPN-конфигов прямо по базе бота — клиентский .conf не нужен.

Для каждого конфига из data/bot.db пересобирает его тем же кодом, что и бот
(src/wireguard.py + параметры сервера из .env), и сверяет с работающим
AmneziaWG-интерфейсом: есть ли пир, совпадают ли allowed-ips, ключ сервера,
параметры обфускации, были ли рукопожатия и трафик.
Секреты (приватные ключи, HeaderProtectionKey) не выводятся.

Запуск на сервере из корня репозитория:
    uv run python scripts/diagnose_configs.py                       # созданные сегодня
    uv run python scripts/diagnose_configs.py desktop               # + имя содержит "desktop"
    uv run python scripts/diagnose_configs.py --since 2026-11-01    # начиная с даты
    uv run python scripts/diagnose_configs.py --all                 # все, включая старые
"""

import argparse
import base64
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey  # noqa: E402

from config import AWG_DEFAULTS, SERVERS  # noqa: E402
from server import _build_command  # noqa: E402

SERVER_SIDE = {
    "S1",
    "S2",
    "S3",
    "S4",
    "H1",
    "H2",
    "H3",
    "H4",
    "HeaderProtectionKey",
    "ContentPaddingAddition",
    "RandomTrailers",
    "DisableCookies",
}
SECRET = {"HeaderProtectionKey"}


def awg(server, *args) -> str:
    cmd = _build_command(server, ["awg", *args])
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15).stdout


def pubkey_from_private(private_b64: str) -> str:
    priv = X25519PrivateKey.from_private_bytes(base64.b64decode(private_b64))
    raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def label(param: str) -> str:
    """HeaderProtectionKey -> 'header protection key' (как печатает `awg show`)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", param).lower()


def interface_params(show_text: str) -> dict:
    params = {}
    for line in show_text.splitlines():
        if line.startswith("peer:"):
            break
        if ": " in line:
            k, v = line.strip().split(": ", 1)
            params[k] = v
    return params


def table(text: str) -> dict:
    """Вывод `awg show <if> <поле>`: '<pubkey>\t<значение...>' -> {pubkey: значение}."""
    out = {}
    for line in text.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            out[parts[0]] = parts[1].strip()
    return out


def norm(value: str) -> str:
    """Выключенный параметр awg show печатает как off/0, а бот его просто не пишет."""
    return "" if value.strip().lower() in ("", "off", "0", "0-0", "false") else value.strip()


def mark(ok: bool) -> str:
    return "✓" if ok else "✗"


def check_server(server) -> dict:
    print(f"\n=== Сервер '{server.key}' ({server.label}), интерфейс {server.interface}")
    try:
        show = awg(server, "show", server.interface)
    except Exception as e:
        print(f"  ✗ не удалось выполнить `awg show {server.interface}`: {e}")
        return {}

    live_pub = awg(server, "show", server.interface, "public-key").strip()
    port = awg(server, "show", server.interface, "listen-port").strip()
    print(f"  {mark(live_pub == server.public_key)} ключ сервера в .env совпадает с интерфейсом")
    if live_pub != server.public_key:
        print(f"      .env: {server.public_key}\n      wg0:  {live_pub}")
    ep_port = server.endpoint.rsplit(":", 1)[-1]
    print(f"  {mark(ep_port == port)} порт Endpoint ({ep_port}) = listen-port ({port})")

    live = interface_params(show)
    bot = dict(server.awg.interface_items())
    # проверяем ВСЕ известные параметры: в т.ч. включённые на сервере, но не в боте
    for param in AWG_DEFAULTS:
        mine, theirs = norm(bot.get(param, "")), norm(live.get(label(param), ""))
        if not mine and not theirs:
            continue
        if mine == theirs:
            shown = "<задан>" if param in SECRET and mine else (mine or "<нет>")
            print(f"  ✓ {param} = {shown}")
            continue
        if param in SECRET:
            mine_s = "<задан>" if mine else "<нет>"
            theirs_s = "<задан>" if theirs else "<нет>"
            if mine and theirs:
                mine_s = "<другой ключ>"
        else:
            mine_s, theirs_s = mine or "<нет>", theirs or "<нет>"
        level = "✗" if param in SERVER_SIDE else "·"
        print(f"  {level} {param}: бот='{mine_s}' сервер='{theirs_s}'")

    return {
        "ips": table(awg(server, "show", server.interface, "allowed-ips")),
        "hs": table(awg(server, "show", server.interface, "latest-handshakes")),
        "ep": table(awg(server, "show", server.interface, "endpoints")),
        "tr": table(awg(server, "show", server.interface, "transfer")),
    }


def since_utc(day: date) -> str:
    """Локальная полночь дня -> строка UTC в формате created_at (SQLite CURRENT_TIMESTAMP)."""
    local_midnight = datetime.combine(day, datetime.min.time()).astimezone()
    return local_midnight.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_args():
    parser = argparse.ArgumentParser(description="Диагностика VPN-конфигов по базе бота")
    parser.add_argument("name", nargs="?", default="", help="подстрока в имени конфига")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--since",
        type=date.fromisoformat,
        default=date.today(),
        help="только конфиги, созданные с этой даты, YYYY-MM-DD (по умолчанию сегодня)",
    )
    group.add_argument("--all", action="store_true", help="без фильтра по дате")
    return parser.parse_args()


def main():
    args = parse_args()
    db_path = os.getenv("BOT_DB_PATH", os.path.join(ROOT, "data", "bot.db"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM vpn_configs WHERE name LIKE ?"
    params = [f"%{args.name}%"]
    filters = []
    if args.name:
        filters.append(f"имя содержит '{args.name}'")
    if not args.all:
        # created_at хранится в UTC, поэтому границу дня переводим из локального времени
        query += " AND created_at >= ?"
        params.append(since_utc(args.since))
        filters.append(f"созданы с {args.since.isoformat()}")
    rows = conn.execute(query + " ORDER BY server, id", params).fetchall()

    suffix = f" ({', '.join(filters)})" if filters else ""
    print(f"База: {db_path}, конфигов: {len(rows)}{suffix}")
    if not rows:
        print("Ничего не найдено. Старые конфиги: --all, другая дата: --since YYYY-MM-DD")
        return

    live_by_server = {}
    for key, server in SERVERS.items():
        if any(r["server"] == key for r in rows):
            live_by_server[key] = check_server(server)

    print("\n=== Конфиги")
    now = int(time.time())
    for r in rows:
        server = SERVERS.get(r["server"])
        print(
            f"\n• '{r['name']}' user={r['user_id']} server={r['server']} "
            f"ip={r['ip_address']} создан={r['created_at']} UTC"
        )
        if not server:
            print("  ✗ сервер не настроен в .env")
            continue
        live = live_by_server.get(r["server"]) or {}
        derived = pubkey_from_private(r["private_key"])
        print(f"  {mark(derived == r['public_key'])} public_key в базе соответствует private_key")
        pub = r["public_key"]
        print(f"  · pubkey: {pub}")
        if pub not in live.get("ips", {}):
            print("  ✗ пира НЕТ на сервере — бот не смог его добавить (см. bot.log)")
            continue
        ips = live["ips"][pub]
        print(f"  {mark(ips == r['ip_address'] + '/32')} allowed-ips на сервере: {ips}")
        hs = int(live["hs"].get(pub, "0") or 0)
        print(
            f"  {mark(hs > 0)} последнее рукопожатие: "
            + (f"{now - hs} с назад" if hs else "ни разу (с момента поднятия интерфейса)")
        )
        print(f"  · endpoint клиента: {live['ep'].get(pub, '(none)')}")
        rx, _, tx = live["tr"].get(pub, "0\t0").partition("\t")
        print(f"  · трафик: принято от клиента {rx} Б, отправлено клиенту {tx} Б")


if __name__ == "__main__":
    main()
