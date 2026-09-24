#!/usr/bin/env bash
# Quick stop script for WoTRR Relay Server
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/relay.sh" stop

