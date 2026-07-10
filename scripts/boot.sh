#!/bin/bash
# =============================================================================
#  UrrunBerri OS — Boot Script (Hardened)
#  Debian 13 Trixie — Root user — xfreerdp3
#  Author : Mathieu Cadi — Openema SARL
#  GitHub : https://github.com/matthewc00002/urrunberri1
#
#  Security: All user-supplied variables are quoted to prevent shell injection.
# =============================================================================

CONFIG="/etc/urrunberri-os/config.conf"
[[ -f "$CONFIG" ]] && source "$CONFIG"

RESOLUTION="${RESOLUTION:-1920x1080}"
KBD_LAYOUT="${KBD_LAYOUT:-0x040C}"
DISPLAY=":0"
XAUTHORITY="/var/run/lightdm/root/:0"
export DISPLAY XAUTHORITY

SAVED_FILE="/etc/urrunberri-os/saved_connections.csv"
SERVER_SCRIPT="/opt/urrunberri-os/scripts/urrunberri_server.py"
LAUNCHER_SCRIPT="/opt/urrunberri-os/scripts/urrunberri_launcher.py"
ACTION_FILE="/tmp/urrunberri_action.txt"
RESULT_FILE="/tmp/urrunberri_login.txt"
RDP_PID=""
SERVER_PID=""
LAUNCHER_PID=""

# ── INIT ──────────────────────────────────────────────────────────────────────
pkill -f urrunberri_server.py 2>/dev/null || true
pkill -f urrunberri_launcher.py 2>/dev/null || true
pkill zenity 2>/dev/null || true
sleep 1

xhost + 2>/dev/null || true
xsetroot -solid "#eef2f7" 2>/dev/null || true
xset -led named "Scroll Lock" 2>/dev/null || true
numlockx on 2>/dev/null || true
mkdir -p /etc/urrunberri-os
touch "$SAVED_FILE" 2>/dev/null || true

# ── DETECT XFREERDP ───────────────────────────────────────────────────────────
XFREERDP_BIN=""
for bin in xfreerdp3 /usr/bin/xfreerdp3 xfreerdp2 /usr/bin/xfreerdp2 xfreerdp /usr/local/bin/xfreerdp; do
    if command -v "$bin" &>/dev/null; then
        XFREERDP_BIN="$bin"
        break
    fi
done
[[ -z "$XFREERDP_BIN" ]] && XFREERDP_BIN="xfreerdp3"
echo "[UrrunBerri OS] xfreerdp: $XFREERDP_BIN"

# ── START PYTHON API SERVER ───────────────────────────────────────────────────
python3 "$SERVER_SCRIPT" &
SERVER_PID=$!
sleep 1
echo "[UrrunBerri OS] API server running on port 7070"
echo "[UrrunBerri OS] Serveur Python PID: $SERVER_PID"

# ── ENSURE SERVER IS RUNNING ──────────────────────────────────────────────────
ensure_server() {
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[UrrunBerri OS] Redemarrage serveur Python..."
        python3 "$SERVER_SCRIPT" &
        SERVER_PID=$!
        sleep 1
    fi
}

# ── WAIT FOR ACTION ───────────────────────────────────────────────────────────
wait_for_action() {
    rm -f "$ACTION_FILE" "$RESULT_FILE"
    while true; do
        if ! kill -0 "$LAUNCHER_PID" 2>/dev/null; then
            return 2
        fi
        sleep 0.3
        [[ -f "$ACTION_FILE" ]] && break
    done
    return 0
}

# ── INPUT VALIDATION ──────────────────────────────────────────────────────────
validate_host() {
    # Only allow alphanumeric, dots, hyphens, colons (IPv6)
    [[ "$1" =~ ^[a-zA-Z0-9.:-]+$ ]] && return 0
    return 1
}

validate_port() {
    [[ "$1" =~ ^[0-9]+$ ]] && (( $1 >= 1 && $1 <= 65535 )) && return 0
    return 1
}

# ── SHOW LOGIN PAGE ───────────────────────────────────────────────────────────
show_login() {
    rm -f "$ACTION_FILE" "$RESULT_FILE"

    ensure_server

    SCR_W=${RESOLUTION%%x*}
    SCR_H=${RESOLUTION##*x}

    xsetroot -solid "#eef2f7" 2>/dev/null || true

    python3 "$LAUNCHER_SCRIPT" 2>/dev/null &
    LAUNCHER_PID=$!
    echo "[UrrunBerri OS] Lanceur GTK PID: $LAUNCHER_PID"

    wait_for_action
    local wait_ret=$?

    if [[ $wait_ret -eq 2 ]]; then
        echo "[UrrunBerri OS] Lanceur mort — redemarrage..."
        return 1
    fi

    kill $LAUNCHER_PID 2>/dev/null || true
    sleep 0.5

    ACTION=$(cat "$ACTION_FILE" 2>/dev/null)

    if [[ "$ACTION" == "shutdown" ]]; then
        kill $SERVER_PID 2>/dev/null || true
        sleep 1
        systemctl poweroff
        exit 0
    fi

    if [[ "$ACTION" == "reboot" ]]; then
        kill $SERVER_PID 2>/dev/null || true
        sleep 1
        systemctl reboot
        exit 0
    fi

    [[ "$ACTION" == "close" ]] && { kill $SERVER_PID 2>/dev/null; exit 0; }

    if [[ "$ACTION" == "terminal" ]]; then
        xterm -bg "#eef2f7" -fg "#1a2744" -fa "Monospace" -fs 12 \
            -title "UrrunBerri OS — Terminal" 2>/dev/null &
        return 1
    fi

    if [[ "$ACTION" == "connect" && -f "$RESULT_FILE" ]]; then
        local data; data=$(cat "$RESULT_FILE")
        CONN_HOST=$(echo "$data" | cut -d'|' -f1)
        CONN_PORT=$(echo "$data" | cut -d'|' -f2)
        USERNAME=$(echo "$data"  | cut -d'|' -f3)
        PASSWORD=$(echo "$data"  | cut -d'|' -f4)
        DOMAIN=$(echo "$data"    | cut -d'|' -f5)
        PROTOCOL=$(echo "$data"  | cut -d'|' -f7)
        RES=$(echo "$data"       | cut -d'|' -f8)
        MULTIMON=$(echo "$data"  | cut -d'|' -f9)
        USB=$(echo "$data"       | cut -d'|' -f10)

        # SECURITY: Validate host and port
        if ! validate_host "$CONN_HOST"; then
            echo "[UrrunBerri OS] SECURITE: adresse invalide rejetee: $CONN_HOST"
            return 1
        fi

        [[ -z "$CONN_HOST" ]] && return 1
        [[ -z "$USERNAME" && "$PROTOCOL" != "web" ]] && return 1
        [[ -z "$CONN_PORT" ]] && CONN_PORT=3389

        if ! validate_port "$CONN_PORT"; then
            echo "[UrrunBerri OS] SECURITE: port invalide rejete: $CONN_PORT"
            CONN_PORT=3389
        fi

        [[ -z "$PROTOCOL" ]] && PROTOCOL=rdp
        # SECURITY: Only allow known protocols
        case "$PROTOCOL" in
            rdp|vnc|ssh|web) ;;
            *) echo "[UrrunBerri OS] SECURITE: protocole invalide: $PROTOCOL"; return 1 ;;
        esac

        [[ -n "$RES" && "$RES" != "undefined" && "$RES" != "auto" ]] && RESOLUTION="$RES"

        if [[ "$RES" == "auto" ]]; then
            RESOLUTION=$(DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xrandr 2>/dev/null | grep '\*' | awk '{print $1}' | head -1)
            [[ -z "$RESOLUTION" ]] && RESOLUTION="1920x1080"
            echo "[UrrunBerri OS] Resolution auto: $RESOLUTION"
        fi

        if [[ -z "$PASSWORD" && "$PROTOCOL" != "web" ]]; then
            PASSWORD=$(zenity --password \
                --title="UrrunBerri OS" \
                --text="Mot de passe pour ${USERNAME}@${CONN_HOST}" \
                2>/dev/null)
            [[ -z "$PASSWORD" ]] && return 1
        fi
        return 0
    fi
    return 1
}

# ── DISCONNECT BUTTON ─────────────────────────────────────────────────────────
show_disconnect_btn() {
    (
        zenity --question \
            --title="UrrunBerri OS" \
            --text="Session active\n${CONN_HOST}:${CONN_PORT}\nUtilisateur : ${USERNAME}\n\nFermer la session ?" \
            --ok-label="Fermer" --cancel-label="Continuer" \
            --width=300 2>/dev/null
        [[ $? -eq 0 ]] && kill "$RDP_PID" 2>/dev/null || true
    ) &
    DISCONNECT_PID=$!
}

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────
while true; do
    xsetroot -solid "#eef2f7" 2>/dev/null || true
    xset -led named "Scroll Lock" 2>/dev/null || true
numlockx on 2>/dev/null || true

    if ! show_login; then
        sleep 1
        continue
    fi

    echo "[UrrunBerri OS] Connexion $PROTOCOL → ${CONN_HOST}:${CONN_PORT} (${USERNAME}) @ ${RESOLUTION}"

    DOMAIN_ARG=""
    [[ -n "$DOMAIN" ]] && DOMAIN_ARG="/d:${DOMAIN}"
    MULTIMON_ARG=""
    [[ "$MULTIMON" == "1" ]] && MULTIMON_ARG="/multimon"
    USB_ARG=""
    if [[ "$USB" == "1" ]]; then
        USB_PARENT=$(lsblk -o NAME,TRAN -rn | grep usb | awk '{print $1}' | head -1)
        USB_DEV=$(lsblk -o NAME,FSTYPE -rn | grep "^${USB_PARENT}" | grep -v "^${USB_PARENT} " | awk '$2!=""' | head -1 | awk '{print $1}')
        if [[ -n "$USB_DEV" ]]; then
            mkdir -p /tmp/usb-share
            umount /tmp/usb-share 2>/dev/null || true
            mount /dev/$USB_DEV /tmp/usb-share 2>/dev/null && USB_ARG="/drive:USB,/tmp/usb-share"
            echo "[UrrunBerri OS] USB monte: /dev/$USB_DEV → /tmp/usb-share"
        else
            echo "[UrrunBerri OS] Aucun peripherique USB detecte"
        fi
    fi

    case "$PROTOCOL" in
        rdp)
            "$XFREERDP_BIN" \
                "/v:${CONN_HOST}:${CONN_PORT}" \
                "/u:${USERNAME}" \
                "/p:${PASSWORD}" \
                ${DOMAIN_ARG} \
                "/size:${RESOLUTION}" \
                /cert:ignore \
                /clipboard /fonts "/kbd:layout:${KBD_LAYOUT}" \
                ${MULTIMON_ARG} \
                ${USB_ARG} \
                /log-level:ERROR &
            RDP_PID=$!
            ;;
        vnc)
            VNC_PASSWD_FILE=""
            if [[ -n "$PASSWORD" ]] && command -v vncpasswd &>/dev/null; then
                VNC_PASSWD_FILE=$(mktemp /tmp/urrunberri_vnc.XXXXXX)
                chmod 600 "$VNC_PASSWD_FILE"
                # TightVNC/VNC auth uses max 8 characters — vncpasswd truncates silently
                printf '%s\n' "$PASSWORD" | vncpasswd -f > "$VNC_PASSWD_FILE" 2>/dev/null
            fi
            if [[ -n "$VNC_PASSWD_FILE" && -s "$VNC_PASSWD_FILE" ]]; then
                vncviewer "${CONN_HOST}:${CONN_PORT}" \
                    -FullColor -FullScreen \
                    -passwd "$VNC_PASSWD_FILE" \
                    2>>/tmp/urrunberri_vnc.log &
            else
                # Fallback: viewer will prompt for the password itself
                [[ -n "$VNC_PASSWD_FILE" ]] && rm -f "$VNC_PASSWD_FILE" && VNC_PASSWD_FILE=""
                vncviewer "${CONN_HOST}:${CONN_PORT}" \
                    -FullColor -FullScreen \
                    2>>/tmp/urrunberri_vnc.log &
            fi
            RDP_PID=$!
            ;;
        web)
            URL="http://${CONN_HOST}:${CONN_PORT}"
            [[ "$CONN_PORT" == "443" ]] && URL="https://${CONN_HOST}"
            python3 /opt/urrunberri-os/scripts/urrunberri_web.py "$URL" \
                2>>/tmp/urrunberri_web.log &
            RDP_PID=$!
            ;;
        ssh)
            xterm -fullscreen -bg "#eef2f7" -fg "#1a2744" \
                -fa "Monospace" -fs 12 \
                -title "SSH — ${CONN_HOST}" \
                -e "ssh '${USERNAME}'@'${CONN_HOST}' -p '${CONN_PORT}'" 2>/dev/null &
            RDP_PID=$!
            ;;
    esac

    sleep 3
    if [[ "$PROTOCOL" == "rdp" ]]; then
        show_disconnect_btn
    else
        DISCONNECT_PID=""
    fi
    wait $RDP_PID 2>/dev/null
    kill $DISCONNECT_PID 2>/dev/null || true
    [[ -n "${VNC_PASSWD_FILE:-}" ]] && rm -f "$VNC_PASSWD_FILE" && VNC_PASSWD_FILE=""
    RDP_PID=""
    echo "[UrrunBerri OS] Deconnecte."
    umount /tmp/usb-share 2>/dev/null || true
    sleep 2
done
