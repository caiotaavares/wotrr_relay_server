# War of the Ring Reconnect (WoTRR) - UDP Relay Server

High-performance, low-latency UDP relay server for **The Lord of the Rings: War of the Ring (2003)**.

Restores peer-to-peer multiplayer across modern internet providers (CGNAT, symmetric NAT, 4G/5G, fiber) with zero manual port-forwarding or Hamachi required.

---

## 🚀 Quick Start (Linux VPS)

The `relay.sh` script automates **native systemd service management** (auto-start on boot, auto-restart on crashes):

### 1. Give Execution Permissions (First Time Only)
```bash
chmod +x *.sh
```

### 2. Start the Server (Managed by systemd)
```bash
./start.sh
# or
./relay.sh start
```
*(On first run, it automatically configures, installs, and enables the `wotrr-relay` systemd service for you!)*

### 3. Check Live Status
```bash
./relay.sh status
```

### 4. View Live Logs (journalctl)
```bash
./relay.sh logs
```
*(Press `Ctrl + C` to exit log stream).*

### 5. Restart the Server
```bash
./relay.sh restart
```

### 6. Stop the Server
```bash
./stop.sh
# or
./relay.sh stop
```

---

## 🛠️ How to Deploy from Windows to VPS

Run this command in **PowerShell** on your local machine:

```powershell
scp -r "C:\Users\caio_\OneDrive\Documentos\WoTRR\git\wotrr_relay_server" wotr@162.141.167.129:/home/wotr/
```
