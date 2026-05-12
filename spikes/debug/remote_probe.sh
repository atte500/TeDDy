#!/bin/bash
echo "--- Environment Info ---"
env | grep -E "HTTP|PROXY|GITHUB"
echo "--- DNS Resolution ---"
nslookup api.payment-gateway.com || echo "DNS Failed"
echo "--- Latency Check ---"
ping -c 4 api.payment-gateway.com || echo "Ping Failed"
echo "--- Trace Route ---"
traceroute api.payment-gateway.com || echo "Traceroute Failed"