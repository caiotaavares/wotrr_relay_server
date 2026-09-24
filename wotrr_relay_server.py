#!/usr/bin/env python3
"""
War of the Ring Reconnect (WoTRR) - Production UDP Relay Server
------------------------------------------------------------------------------
High-performance, low-latency zero-config UDP relay server for Liquid Entertainment's
'The Lord of the Rings: War of the Ring' (2003).

Features:
- Full Multi-Room (1v1, 2v2, 3v3, 4v4) isolation based on real destination IP (Protocol V3).
- Dual-socket awareness: routes Staging Query (13139) and Battle Gameplay (7175) independently.
- Production logging with RotatingFileHandler (bounded disk usage, zero unbounded log growth).
- Clean console output: suppresses per-packet spam in production while capturing all lifecycle,
  connection, error, and periodic traffic statistics.
- Verbose per-packet debugging togglable via '--debug' flag.
- Rate-limited logging for unmapped / waiting endpoints.
- Automatic garbage collection of disconnected players (180s inactivity timeout).
- Backward compatible with Protocol V2 (8-byte) and V1 (4-byte) headers.
"""

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import socket
import struct
import sys
import time

DEFAULT_PORT = 7175
DEFAULT_BIND = "0.0.0.0"
DEFAULT_TIMEOUT = 180.0     # 3 minutes of inactivity before cleaning up player
DEFAULT_LOG_FILE = "wotrr_relay.log"
DEFAULT_MAX_LOG_MB = 10     # Rotate after 10 MB
DEFAULT_BACKUP_COUNT = 5    # Keep 5 backup logs (~50 MB max storage)
STATS_INTERVAL = 60.0       # Log traffic summary every 60 seconds
WAIT_LOG_THROTTLE = 10.0    # Log waiting packets at most once per 10s per destination

# Global running flag for graceful shutdown
g_running = True


def setup_logger(log_file, debug_mode, max_mb, backup_count):
    """Configures structured dual-output logging (Rotating File + Console)."""
    logger = logging.getLogger("WoTRR-Relay")
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Rotating File Handler (bounded disk usage)
    try:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=int(max_mb * 1024 * 1024),
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[!] Warning: Could not create log file '{log_file}': {e}", file=sys.stderr)

    # 2. Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    console_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def format_bytes(num_bytes):
    """Returns human-readable string for byte quantities."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def format_uptime(seconds):
    """Formats uptime seconds into HH:MM:SS format."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def handle_shutdown(signum, frame):
    """Signal handler for graceful shutdown (SIGINT / SIGTERM)."""
    global g_running
    g_running = False


def main():
    parser = argparse.ArgumentParser(
        description="War of the Ring - Production UDP Multi-Room Relay Server"
    )
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help=f"UDP Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("-b", "--bind", type=str, default=DEFAULT_BIND, help=f"Bind IP address (default: {DEFAULT_BIND})")
    parser.add_argument("-t", "--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Inactivity timeout in seconds (default: {DEFAULT_TIMEOUT}s)")
    parser.add_argument("-l", "--log-file", type=str, default=DEFAULT_LOG_FILE, help=f"Log file path (default: {DEFAULT_LOG_FILE})")
    parser.add_argument("--max-log-mb", type=float, default=DEFAULT_MAX_LOG_MB, help=f"Max log file size in MB before rotation (default: {DEFAULT_MAX_LOG_MB}MB)")
    parser.add_argument("--log-backups", type=int, default=DEFAULT_BACKUP_COUNT, help=f"Number of rotated log backups to retain (default: {DEFAULT_BACKUP_COUNT})")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable verbose per-packet routing debug output")

    args = parser.parse_args()

    # Resolve log path relative to script directory if relative
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = args.log_file if os.path.isabs(args.log_file) else os.path.join(script_dir, args.log_file)

    # Initialize logger
    logger = setup_logger(log_path, args.debug, args.max_log_mb, args.log_backups)

    # Register signal handlers for clean process management (systemd, docker, Ctrl+C)
    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    # Create UDP Socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Optimize kernel socket buffers for high-burst RTS lockstep simulation
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)
        except Exception as e:
            logger.debug(f"Could not expand socket buffer: {e}")

        sock.bind((args.bind, args.port))
        sock.settimeout(1.0)  # 1-second timeout allows graceful shutdown check
    except Exception as e:
        logger.critical(f"FATAL: Failed to bind UDP socket on {args.bind}:{args.port} - {e}")
        sys.exit(1)

    # Startup Banner
    logger.info("==================================================================")
    logger.info("  War of the Ring Reconnect (WoTRR) - Production Relay Server")
    logger.info("==================================================================")
    logger.info(f"Listening on       : {args.bind}:{args.port} (UDP)")
    logger.info(f"Inactivity Timeout : {args.timeout:.0f} seconds")
    logger.info(f"Logging Destination: {os.path.abspath(log_path)} (Max: {args.max_log_mb}MB x {args.log_backups})")
    logger.info(f"Verbose Debug Mode : {'ENABLED (per-packet logs active)' if args.debug else 'DISABLED (production mode)'}")
    logger.info("Server is ready and awaiting incoming player connections...")

    # Player session table: ip_str -> dict
    players = {}
    
    # Rate-limiter dictionary for "waiting for opponent" logs: (src_ip, target_ip) -> last_log_time
    wait_log_times = {}

    # Traffic Metrics
    start_time = time.time()
    last_cleanup = start_time
    last_stats = start_time

    stat_total_pkts = 0
    stat_query_pkts = 0
    stat_game_pkts = 0
    stat_relayed_bytes = 0
    stat_wait_pkts = 0
    stat_errors = 0

    global g_running
    while g_running:
        try:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                # Timeout tick: execute periodic housekeeping and check g_running
                now = time.time()
                # 1. Periodic cleanup of stale players
                if now - last_cleanup > 30.0:
                    last_cleanup = now
                    stale_ips = [k for k, v in players.items() if now - v['last_seen'] > args.timeout]
                    for s_ip in stale_ips:
                        del players[s_ip]
                        logger.info(f"[-] [DISCONNECT] Player {s_ip} timed out after {args.timeout:.0f}s of inactivity. Active players: {len(players)}")

                # 2. Periodic traffic summary (every 60 seconds)
                if now - last_stats > STATS_INTERVAL:
                    last_stats = now
                    uptime_str = format_uptime(now - start_time)
                    active_count = len(players)
                    if active_count > 0 or stat_total_pkts > 0:
                        logger.info(
                            f"[STATS] Uptime: {uptime_str} | Active Players: {active_count} | "
                            f"Relayed: {stat_total_pkts} pkts ({format_bytes(stat_relayed_bytes)}) | "
                            f"Query: {stat_query_pkts} | Game: {stat_game_pkts} | Waiting: {stat_wait_pkts} | Errors: {stat_errors}"
                        )
                continue

            ip, port = addr[0], addr[1]
            now = time.time()
            data_len = len(data)

            # 1. Register or update player connection
            is_new = (ip not in players)
            if is_new:
                players[ip] = {
                    'last_seen': now,
                    'last_addr': addr,
                    'last_query': None,
                    'last_game': None,
                    'pkts_sent': 0,
                    'pkts_recv': 0
                }
                logger.info(f"[+] [CONNECT] Player registered: {ip}:{port} | Total Active Players: {len(players)}")

            p = players[ip]
            p['last_seen'] = now
            p['last_addr'] = addr
            p['pkts_sent'] += 1

            # 2. Handle DLL Proactive Hole-Punching & Health Pings
            if data == b"WOTR_HELLO":
                p['last_query'] = addr
                logger.info(f"[*] [HELLO] Staging Query Socket (13139) mapped for player {ip}:{port}")
                continue

            if data == b"WOTR_HELLO_GAME":
                p['last_game'] = addr
                logger.info(f"[*] [HELLO_GAME] Battle Gameplay Socket (7175) mapped for player {ip}:{port} (Launch Ready)")
                continue

            # 3. Decode Protocol Headers
            src_port = 0
            dst_port = 0
            dst_ip = None

            if data_len >= 16 and data[0:2] == b"WR" and data[2] == 0x03:
                # Protocol V3 (16-byte header): Multi-Room Routing by Destination IP
                try:
                    src_port = struct.unpack("!H", data[4:6])[0]
                    dst_port = struct.unpack("!H", data[6:8])[0]
                    dst_ip_bytes = data[12:16]
                    dst_ip = socket.inet_ntoa(dst_ip_bytes)

                    # Stamp the sender's real public IP into srcIP field for the receiver
                    src_ip_bytes = socket.inet_aton(ip)
                    data = data[:8] + src_ip_bytes + data[12:]
                except struct.error:
                    stat_errors += 1
                    logger.warning(f"[!] Malformed V3 header received from {ip}:{port}")
                    continue

            elif data_len >= 8 and data[0:2] == b"WR" and data[2] == 0x02:
                # Protocol V2 (8-byte header): Legacy 1v1 Multi-Socket
                try:
                    src_port = struct.unpack("!H", data[4:6])[0]
                    dst_port = struct.unpack("!H", data[6:8])[0]
                except struct.error:
                    stat_errors += 1
                    continue

            elif data_len >= 4 and data[0:2] == b"WR":
                # Protocol V1 (4-byte header): Legacy
                try:
                    dst_port = struct.unpack("!H", data[2:4])[0]
                    src_port = dst_port
                except struct.error:
                    stat_errors += 1
                    continue

            # Update sender socket mapping (Query vs Game)
            if src_port == 13139:
                p['last_query'] = addr
            elif src_port != 0:
                p['last_game'] = addr

            # 4. Resolve Target Destination
            target_p = None
            target_ip = None

            if dst_ip and dst_ip != "0.0.0.0":
                # Strict Multi-Room Routing (Protocol V3):
                # Only deliver to the requested opponent. Never bleed packets into other rooms!
                if dst_ip in players and dst_ip != ip:
                    target_p = players[dst_ip]
                    target_ip = dst_ip
                else:
                    target_ip = dst_ip
                    target_p = None
            else:
                # Legacy Fallback (Protocol V1 / V2 without dstIP):
                other_ips = [k for k in players.keys() if k != ip]
                if other_ips:
                    target_ip = other_ips[0]
                    target_p = players[target_ip]

            # 5. Forward Packet to Target Endpoint
            if target_p:
                if dst_port == 13139 and target_p['last_query']:
                    target_addr = target_p['last_query']
                    tag = "QUERY"
                    stat_query_pkts += 1
                elif dst_port != 13139 and dst_port != 0 and target_p['last_game']:
                    target_addr = target_p['last_game']
                    tag = "GAME"
                    stat_game_pkts += 1
                else:
                    target_addr = target_p['last_addr']
                    tag = "DIRECT"
                    if dst_port == 13139:
                        stat_query_pkts += 1
                    else:
                        stat_game_pkts += 1

                try:
                    sock.sendto(data, target_addr)
                    target_p['pkts_recv'] += 1
                    stat_total_pkts += 1
                    stat_relayed_bytes += data_len

                    # Per-packet logs only in DEBUG mode to prevent log flooding
                    logger.debug(
                        f"[{tag}] {ip}:{port} -> {target_addr[0]}:{target_addr[1]} "
                        f"(srcPort:{src_port} -> dstPort:{dst_port}) [{data_len} bytes]"
                    )
                except OSError as e:
                    stat_errors += 1
                    logger.warning(f"[!] Socket error forwarding to {target_addr[0]}:{target_addr[1]}: {e}")

            else:
                # Target opponent is not yet connected or mapped
                stat_wait_pkts += 1
                pair_key = (ip, target_ip or "unassigned")
                last_log = wait_log_times.get(pair_key, 0.0)

                # Rate-limit "waiting" logs to once every 10 seconds per target pair
                if now - last_log > WAIT_LOG_THROTTLE:
                    wait_log_times[pair_key] = now
                    logger.info(
                        f"[WAITING] {ip}:{port} is waiting for opponent ({target_ip or 'another player'}). "
                        f"Active players: {len(players)}"
                    )
                else:
                    logger.debug(f"[WAITING-THROTTLED] {ip}:{port} waiting for {target_ip} ({data_len} bytes)")

        except KeyboardInterrupt:
            break
        except Exception as e:
            stat_errors += 1
            logger.error(f"[!] Unexpected error in main loop: {e}", exc_info=args.debug)

    # Clean Server Shutdown
    logger.info("==================================================================")
    logger.info("Relay server shutting down cleanly...")
    uptime_final = format_uptime(time.time() - start_time)
    logger.info(
        f"Final Summary: Uptime: {uptime_final} | Relayed Packets: {stat_total_pkts} ({format_bytes(stat_relayed_bytes)}) | "
        f"Query: {stat_query_pkts} | Game: {stat_game_pkts} | Errors: {stat_errors}"
    )
    try:
        sock.close()
    except Exception:
        pass
    logger.info("Socket closed. Goodbye!")


if __name__ == "__main__":
    main()