#!/bin/bash
# WHISPER Tunnel Server - iptables setup script
# Must be run as root

set -e

# Configuration
INTERNAL_PORT=5667
EXTERNAL_START=6000
EXTERNAL_END=19999
TUN_INTERFACE="whispertun0"
TUN_NETWORK="10.99.0.0/24"

echo "Setting up iptables for WHISPER Tunnel Server..."

# Flush existing rules
echo "Flushing existing rules..."
iptables -t nat -F
iptables -t mangle -F
iptables -F

# Set default policies
echo "Setting default policies..."
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback
echo "Allowing loopback..."
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established connections
echo "Allowing established connections..."
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (adjust port as needed)
echo "Allowing SSH..."
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow ICMP (ping)
echo "Allowing ICMP..."
iptables -A INPUT -p icmp -j ACCEPT

# Setup DNAT for UDP port range
echo "Setting up DNAT for UDP ports $EXTERNAL_START-$EXTERNAL_END -> $INTERNAL_PORT..."
iptables -t nat -A PREROUTING -p udp --dport $EXTERNAL_START:$EXTERNAL_END -j DNAT --to-destination :$INTERNAL_PORT

# Allow incoming UDP on port range and internal port
echo "Allowing UDP on ports $EXTERNAL_START-$EXTERNAL_END and $INTERNAL_PORT..."
iptables -A INPUT -p udp --dport $EXTERNAL_START:$EXTERNAL_END -j ACCEPT
iptables -A INPUT -p udp --dport $INTERNAL_PORT -j ACCEPT

# Setup NAT for TUN interface
echo "Setting up NAT for $TUN_INTERFACE..."
iptables -t nat -A POSTROUTING -s $TUN_NETWORK -o eth0 -j MASQUERADE

# Allow forwarding for TUN interface
echo "Allowing forwarding for $TUN_INTERFACE..."
iptables -A FORWARD -i $TUN_INTERFACE -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o $TUN_INTERFACE -m state --state ESTABLISHED,RELATED -j ACCEPT

# Enable IP forwarding
echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Save rules (if iptables-persistent is installed)
if command -v iptables-save > /dev/null; then
    echo "Saving iptables rules..."
    iptables-save > /etc/iptables/rules.v4
fi

echo "iptables setup completed!"
echo ""
echo "Summary:"
echo "  - DNAT: UDP $EXTERNAL_START-$EXTERNAL_END -> :$INTERNAL_PORT"
echo "  - NAT: $TUN_NETWORK -> MASQUERADE"
echo "  - IP forwarding enabled"
