#!/bin/bash
# Сверяет клиентский .conf с работающим AmneziaWG-интерфейсом на этом сервере.
# Секреты (PrivateKey, HeaderProtectionKey) не выводятся — только "совпадает/нет".
#
# Использование (на VPN-сервере, от root):
#   bash scripts/check_client_conf.sh /path/to/vpn_name.conf [интерфейс=wg0] [секунд_слушать=20]

set -uo pipefail

CONF="${1:?укажите путь к клиентскому .conf}"
IFACE="${2:-wg0}"
LISTEN_SECONDS="${3:-20}"

ok() { echo "  ✓ $*"; }
bad() { echo "  ✗ $*"; FAILED=1; }
info() { echo "  · $*"; }
FAILED=0

# значение ключа из секции конфига: conf_get <section> <key>
conf_get() {
    awk -v sec="[$1]" -v key="$2" '
        /^\[/ { in_sec = ($0 == sec); next }
        in_sec {
            split($0, kv, "=")
            k = kv[1]; gsub(/[ \t\r]/, "", k)
            if (k == key) { sub(/^[^=]*=[ \t]*/, ""); sub(/[ \t\r]+$/, ""); print; exit }
        }' "$CONF"
}

# значение из `awg show <iface>` по ключу конфига: HeaderProtectionKey -> "header protection key"
show_get() {
    local label
    label=$(echo "$1" | sed -E 's/([a-z0-9])([A-Z])/\1 \2/g' | tr '[:upper:]' '[:lower:]')
    awg show "$IFACE" | awk -v l="$label" '
        /^peer:/ { exit }
        { line = $0; sub(/^[ \t]+/, "", line)
          if (index(line, l ": ") == 1) { print substr(line, length(l) + 3); exit } }'
}

echo "== Интерфейс $IFACE"
if ! awg show "$IFACE" >/dev/null 2>&1; then
    echo "  ✗ интерфейс $IFACE не найден (awg show)"; exit 1
fi
ok "поднят, $(awg --version 2>/dev/null | head -1)"

echo "== Ключ сервера"
SRV_PUB=$(awg show "$IFACE" public-key)
CONF_SRV_PUB=$(conf_get Peer PublicKey)
[ "$SRV_PUB" = "$CONF_SRV_PUB" ] && ok "[Peer] PublicKey совпадает" \
    || bad "[Peer] PublicKey в конфиге ($CONF_SRV_PUB) != ключ сервера ($SRV_PUB) → WG_SERVER_PUBLIC_KEY_NL в .env"

echo "== Endpoint"
ENDPOINT=$(conf_get Peer Endpoint)
PORT=$(awg show "$IFACE" listen-port)
[ "${ENDPOINT##*:}" = "$PORT" ] && ok "порт $PORT совпадает" \
    || bad "порт в Endpoint (${ENDPOINT##*:}) != listen-port ($PORT)"
info "Endpoint в конфиге: ${ENDPOINT%:*}; IP сервера: $(hostname -I 2>/dev/null) / внешний: $(curl -s -m 5 https://ifconfig.me || echo '?')"

echo "== Пир клиента"
CLIENT_PRIV=$(conf_get Interface PrivateKey)
CLIENT_PUB=$(echo "$CLIENT_PRIV" | awg pubkey 2>/dev/null)
CLIENT_ADDR=$(conf_get Interface Address)
if [ -z "$CLIENT_PUB" ]; then
    bad "не удалось вычислить публичный ключ из PrivateKey"
elif awg show "$IFACE" allowed-ips | grep -q "^$CLIENT_PUB"; then
    PEER_IPS=$(awg show "$IFACE" allowed-ips | awk -v k="$CLIENT_PUB" '$1 == k { $1 = ""; sub(/^ /, ""); print }')
    ok "пир $CLIENT_PUB есть на сервере"
    [ "$PEER_IPS" = "$CLIENT_ADDR" ] && ok "allowed-ips $PEER_IPS = Address" \
        || bad "allowed-ips на сервере ($PEER_IPS) != Address в конфиге ($CLIENT_ADDR)"
else
    bad "пира $CLIENT_PUB НЕТ на сервере — бот не добавил его или он удалён"
fi

echo "== Параметры обфускации"
for key in Jc Jmin Jmax S1 S2 S3 S4 H1 H2 H3 H4 I1 I2 I3 I4 I5 HeaderProtectionKey \
    ContentPaddingAddition RandomTrailers DisableCookies RekeyAfterTime RekeyTimeout \
    RejectAfterTime KeepaliveTimeout MaxHandshakeAttempts; do
    c=$(conf_get Interface "$key")
    s=$(show_get "$key")
    [ -z "$c" ] && [ -z "$s" ] && continue
    case "$key" in
        Jc | Jmin | Jmax | I[1-5] | RekeyAfterTime | RekeyTimeout | RejectAfterTime | KeepaliveTimeout | MaxHandshakeAttempts)
            side="client-side" ;;
        *) side="server-side" ;;
    esac
    shown_c="$c"; shown_s="$s"
    if [ "$key" = "HeaderProtectionKey" ]; then
        shown_c="${c:+<задан>}"; shown_s="${s:+<задан>}"
        [ -n "$c" ] && [ -n "$s" ] && [ "$c" != "$s" ] && shown_c="<другой ключ>"
    fi
    if [ "$c" = "$s" ]; then
        ok "$key = ${shown_c:-<нет>}"
    elif [ "$side" = "server-side" ]; then
        bad "$key: конфиг='${shown_c:-<нет>}' сервер='${shown_s:-<нет>}' (обязан совпадать)"
    else
        info "$key: конфиг='${shown_c:-<нет>}' сервер='${shown_s:-<нет>}' (client-side, допустимо)"
    fi
done
# ключи в конфиге, которых сервер не знает
for key in $(awk '/^\[Interface\]/{f=1;next} /^\[/{f=0} f && /=/{gsub(/[ \t]/,"");split($0,a,"=");print a[1]}' "$CONF"); do
    case "$key" in PrivateKey | Address | DNS | MTU) continue ;; esac
    [ -z "$(show_get "$key")" ] && info "$key есть в конфиге, но не виден в awg show"
done

echo "== Файрвол (порт $PORT/udp)"
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw status | grep -q "$PORT" && ok "ufw: правило для $PORT есть" || bad "ufw активен, правила для $PORT/udp нет"
fi
iptables -S INPUT 2>/dev/null | grep -E -- "-P INPUT (DROP|REJECT)" >/dev/null &&
    info "политика iptables INPUT = DROP; правила с $PORT: $(iptables -S INPUT | grep -c "$PORT")"

echo "== Трафик: подключитесь клиентом в течение ${LISTEN_SECONDS}с..."
if command -v tcpdump >/dev/null; then
    DUMP=$(timeout "$LISTEN_SECONDS" tcpdump -nni any -l "udp port $PORT" 2>/dev/null)
    IN=$(echo "$DUMP" | grep -c "> [0-9.]*\.$PORT:" || true)
    OUT=$(echo "$DUMP" | grep -c "\.$PORT > " || true)
    info "входящих пакетов: $IN, исходящих: $OUT"
    if [ "$IN" -eq 0 ]; then
        bad "пакеты от клиента не доходят → Endpoint/IP, файрвол провайдера или блокировка в сети клиента"
    elif [ "$OUT" -eq 0 ]; then
        bad "пакеты приходят, сервер не отвечает → параметры/ключи не совпадают (см. выше)"
    else
        ok "сервер отвечает"
    fi
    awg show "$IFACE" latest-handshakes | grep "^$CLIENT_PUB" | awk '{ print "  · latest handshake (unix):", $2 }'
else
    info "tcpdump не установлен: apt install tcpdump"
fi

echo
[ "$FAILED" -eq 0 ] && echo "Явных расхождений не найдено." || echo "Есть расхождения (✗) — их и нужно исправить."
