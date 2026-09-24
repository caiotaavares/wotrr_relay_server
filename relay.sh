#!/usr/bin/env bash
# ==============================================================================
# WoTRR (War of the Ring Reconnect) Relay Server - systemd Management Script
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="wotrr-relay"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_FILE="$DIR/wotrr_relay.log"

# Locate the Python script (prefers wotrr_relay_server.py)
if [ -f "$DIR/wotrr_relay_server.py" ]; then
    SCRIPT_NAME="wotrr_relay_server.py"
elif [ -f "$DIR/wotr_relay_server.py" ]; then
    SCRIPT_NAME="wotr_relay_server.py"
else
    echo "[!] Error: wotrr_relay_server.py not found in $DIR"
    exit 1
fi

PYTHON_BIN="$(command -v python3 || echo "/usr/bin/python3")"
CURRENT_USER="$(whoami)"

install_service() {
    echo "[*] Configuring systemd service '${SERVICE_NAME}'..."
    echo "    Script Directory : $DIR"
    echo "    Python Binary    : $PYTHON_BIN"
    echo "    Service User     : $CURRENT_USER"

    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=War of the Ring Reconnect (WoTRR) UDP Relay Server
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${DIR}
ExecStart=${PYTHON_BIN} ${DIR}/${SCRIPT_NAME}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    echo "[*] Reloading systemd daemon..."
    sudo systemctl daemon-reload
    echo "[*] Enabling service on system boot..."
    sudo systemctl enable "${SERVICE_NAME}"
    echo "[+] Service '${SERVICE_NAME}' successfully installed and enabled!"
}

ensure_installed() {
    if [ ! -f "$SERVICE_FILE" ] || ! grep -q "$DIR" "$SERVICE_FILE" 2>/dev/null; then
        echo "[*] Configuring / updating '${SERVICE_NAME}' in systemd to point to $DIR..."
        install_service
    fi
}

start_service() {
    ensure_installed
    echo "[*] Starting ${SERVICE_NAME} via systemd..."
    sudo systemctl start "${SERVICE_NAME}"
    sleep 1
    sudo systemctl status "${SERVICE_NAME}" --no-pager
}

stop_service() {
    echo "[*] Stopping ${SERVICE_NAME} via systemd..."
    sudo systemctl stop "${SERVICE_NAME}"
    echo "[+] ${SERVICE_NAME} stopped."
}

restart_service() {
    ensure_installed
    echo "[*] Restarting ${SERVICE_NAME} via systemd..."
    sudo systemctl restart "${SERVICE_NAME}"
    sleep 1
    sudo systemctl status "${SERVICE_NAME}" --no-pager
}

status_service() {
    if [ -f "$SERVICE_FILE" ]; then
        sudo systemctl status "${SERVICE_NAME}" --no-pager
    else
        echo "[-] Service '${SERVICE_NAME}' is not installed in systemd."
        echo "    Run '$0 install' or '$0 start' to set it up."
    fi
}

show_logs() {
    echo "[*] Showing live systemd journal logs (Press Ctrl+C to exit)..."
    journalctl -u "${SERVICE_NAME}" -f
}

case "$1" in
    install)
        install_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "=================================================================="
        echo "  WoTRR Relay Server - systemd Control Tool"
        echo "=================================================================="
        echo "Usage: $0 {start|stop|restart|status|logs|install}"
        echo ""
        echo "Commands:"
        echo "  start    - Start service as a systemd daemon (auto-installs if needed)"
        echo "  stop     - Stop the running systemd daemon"
        echo "  restart  - Restart the systemd daemon"
        echo "  status   - View live service status (active/running, memory, PID)"
        echo "  logs     - Follow live output (journalctl -u ${SERVICE_NAME} -f)"
        echo "  install  - Install / update systemd service configuration"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 status"
        echo "  $0 logs"
        echo "  $0 stop"
        exit 1
        ;;
esac
