#!/usr/bin/env bash
# Quick launch script for WoTRR Relay Server
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/relay.sh" start "$@"

