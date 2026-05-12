#!/bin/bash
set -e

echo "##[group]remote_probe: Environment Inspection"
echo "Current User: $(whoami)"
echo "Network Interfaces:"
ip addr
echo "Listening Ports:"
netstat -tulpn || ss -tulpn
echo "Environment Variables (Filtered):"
env | grep -E "DB_|POSTGRES|HOST"
echo "##[endgroup]"