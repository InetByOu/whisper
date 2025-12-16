#!/bin/bash
# Setup iptables for UDTUN Server

set -e

# Configuration
UDP_PORT_START=6000
UDP_PORT_END=19999
INTERNAL_PORT=5667
TUN_INTERFACE="udtun0"
EXTERNAL_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root"
        exit 1
    fi
}

setup_sysctl() {
    log_info "Setting up sysctl parameters..."
    
    # Increase UDP buffer sizes
    sysctl -w net.core.rmem_max=4194304
    sysctl -w net.core.wmem_max=4194304
    sysctl -w net.core.rmem_default=262144
    sysctl -w net.core.wmem_default=262144
    
    # Enable IP forwarding
    sysctl -w net.ipv4.ip_forward=1
    sysctl -w net.ipv6.conf.all.forwarding=1
    
    # TCP optimizations (for server-side connections)
    sysctl -w net.ipv4.tcp_congestion_control=bbr
    sysctl -w net.ipv4.tcp_notsent_lowat=16384
    sysctl -w net.core.default_qdisc=fq
    
    # Save to /etc/sysctl.conf
    cat >> /etc/sysctl.conf << EOF
# UDTUN Optimizations
net.core.rmem_max=4194304
net.core.wmem_max=4194304
net.core.rmem_default=262144
net.core.wmem_default=262144
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
EOF
    
    sysctl -p
}

setup_iptables() {
    log_info "Setting up iptables rules..."
    
    # Flush existing rules
    iptables -F
    iptables -t nat -F
    
    # Default policies
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT ACCEPT
    
    # Allow established connections
    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
    
    # Allow loopback
    iptables -A INPUT -i lo -j ACCEPT
    
    # Allow SSH
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT
    
    # Allow ICMP (ping)
    iptables -A INPUT -p icmp -j ACCEPT
    
    # Allow UDP port range for blind probing
    iptables -A INPUT -p udp --dport ${UDP_PORT_START}:${UDP_PORT_END} -j ACCEPT
    
    # DNAT: Redirect UDP ports to internal service
    iptables -t nat -A PREROUTING -p udp --dport ${UDP_PORT_START}:${UDP_PORT_END} \
              -j DNAT --to-destination :${INTERNAL_PORT}
    
    # Allow internal port
    iptables -A INPUT -p udp --dport ${INTERNAL_PORT} -j ACCEPT
    
    # Allow forwarding from TUN to internet
    iptables -A FORWARD -i ${TUN_INTERFACE} -o ${EXTERNAL_INTERFACE} -j ACCEPT
    iptables -A FORWARD -i ${EXTERNAL_INTERFACE} -o ${TUN_INTERFACE} -m state \
              --state ESTABLISHED,RELATED -j ACCEPT
    
    # NAT for TUN interface
    iptables -t nat -A POSTROUTING -o ${EXTERNAL_INTERFACE} -j MASQUERADE
    
    # Save rules
    iptables-save > /etc/iptables/rules.v4
    
    log_info "Iptables rules applied and saved"
}

setup_ufw() {
    log_info "Configuring UFW..."
    
    # Disable UFW if enabled (we use iptables directly)
    ufw --force disable
    
    # Or configure UFW if preferred:
    # ufw --force reset
    # ufw default deny incoming
    # ufw default allow outgoing
    # ufw allow 22/tcp
    # ufw allow 6000:19999/udp
    # ufw allow 5667/udp
    # ufw --force enable
}

cleanup_old() {
    log_info "Cleaning up old rules..."
    
    # Remove old DNAT rules
    iptables -t nat -S PREROUTING | grep "udp.*${UDP_PORT_START}:${UDP_PORT_END}" | \
        while read rule; do
            iptables -t nat -D PREROUTING ${rule#*-A PREROUTING }
        done 2>/dev/null || true
    
    # Remove old INPUT rules for our ports
    iptables -S INPUT | grep "udp.*dport.*${UDP_PORT_START}:${UDP_PORT_END}" | \
        while read rule; do
            iptables -D INPUT ${rule#*-A INPUT }
        done 2>/dev/null || true
    
    # Remove old TUN interface rules
    iptables -S FORWARD | grep "${TUN_INTERFACE}" | \
        while read rule; do
            iptables -D FORWARD ${rule#*-A FORWARD }
        done 2>/dev/null || true
}

install_service() {
    log_info "Installing systemd service..."
    
    cat > /etc/systemd/system/udtun.service << EOF
[Unit]
Description=UDTUN UDP Tunneling Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/udtun/server
ExecStart=/usr/bin/python3 /opt/udtun/server/main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/log/udtun

# Performance
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable udtun.service
    
    log_info "Service installed. Start with: systemctl start udtun"
}

show_status() {
    log_info "Current configuration:"
    echo "UDP Port Range: ${UDP_PORT_START}-${UDP_PORT_END}"
    echo "Internal Port: ${INTERNAL_PORT}"
    echo "TUN Interface: ${TUN_INTERFACE}"
    echo "External Interface: ${EXTERNAL_INTERFACE}"
    echo ""
    
    log_info "Current iptables rules:"
    echo "=== PREROUTING ==="
    iptables -t nat -L PREROUTING -n -v
    echo ""
    echo "=== INPUT ==="
    iptables -L INPUT -n -v
    echo ""
    echo "=== FORWARD ==="
    iptables -L FORWARD -n -v
    echo ""
    echo "=== POSTROUTING ==="
    iptables -t nat -L POSTROUTING -n -v
}

case "$1" in
    install)
        check_root
        cleanup_old
        setup_sysctl
        setup_iptables
        install_service
        show_status
        ;;
    remove)
        check_root
        systemctl stop udtun.service 2>/dev/null || true
        systemctl disable udtun.service 2>/dev/null || true
        rm -f /etc/systemd/system/udtun.service
        systemctl daemon-reload
        
        # Remove iptables rules
        cleanup_old
        iptables -t nat -D POSTROUTING -o ${EXTERNAL_INTERFACE} -j MASQUERADE 2>/dev/null || true
        
        # Remove TUN interface
        ip link delete ${TUN_INTERFACE} 2>/dev/null || true
        
        log_info "UDTUN removed"
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {install|remove|status}"
        exit 1
        ;;
esac
