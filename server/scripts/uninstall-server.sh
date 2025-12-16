#!/bin/bash
# UDTUN Server Uninstall Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} Please run as root"
        exit 1
    fi
}

stop_service() {
    print_info "Stopping UDTUN service..."
    systemctl stop udtun-server.service 2>/dev/null || true
    systemctl disable udtun-server.service 2>/dev/null || true
}

remove_service() {
    print_info "Removing systemd service..."
    rm -f /etc/systemd/system/udtun-server.service
    systemctl daemon-reload
}

cleanup_iptables() {
    print_info "Cleaning up iptables rules..."
    
    # Remove UDTUN specific rules
    iptables -D INPUT -p udp --dport 6000:19999 -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -p udp --dport 5667 -j ACCEPT 2>/dev/null || true
    
    iptables -t nat -D PREROUTING -p udp --dport 6000:19999 -j DNAT --to-destination :5667 2>/dev/null || true
    
    # Get external interface
    EXT_IF=$(ip route | grep default | awk '{print $5}' | head -1 2>/dev/null)
    if [ -n "$EXT_IF" ]; then
        iptables -t nat -D POSTROUTING -o $EXT_IF -j MASQUERADE 2>/dev/null || true
        iptables -D FORWARD -i udtun0 -o $EXT_IF -j ACCEPT 2>/dev/null || true
        iptables -D FORWARD -i $EXT_IF -o udtun0 -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
    fi
}

remove_tun_interface() {
    print_info "Removing TUN interface..."
    ip link delete udtun0 2>/dev/null || true
}

remove_files() {
    print_info "Removing files..."
    
    # Remove server files
    rm -rf /opt/udtun/server
    
    # Remove config
    rm -rf /etc/udtun
    
    # Remove logs
    rm -rf /var/log/udtun
    
    # Check if /opt/udtun is empty
    if [ -d /opt/udtun ] && [ -z "$(ls -A /opt/udtun)" ]; then
        rm -rf /opt/udtun
    fi
}

show_summary() {
    echo ""
    echo "=" * 50
    echo "UDTUN SERVER UNINSTALLATION COMPLETE"
    echo "=" * 50
    echo ""
    echo "The following have been removed:"
    echo "✓ UDTUN Server files"
    echo "✓ Systemd service"
    echo "✓ iptables rules"
    echo "✓ TUN interface"
    echo "✓ Configuration files"
    echo "✓ Log files"
    echo ""
    echo "Note: Kernel modules and sysctl settings remain."
    echo "To remove them manually:"
    echo "  rm /etc/modules-load.d/tun.conf"
    echo "  Remove udtun settings from /etc/sysctl.conf"
    echo ""
    echo "=" * 50
}

main() {
    print_info "Starting UDTUN Server Uninstallation"
    echo ""
    
    # Check root
    check_root
    
    # Confirm
    read -p "Are you sure you want to uninstall UDTUN Server? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstallation cancelled"
        exit 0
    fi
    
    # Stop service
    stop_service
    
    # Remove service
    remove_service
    
    # Cleanup iptables
    cleanup_iptables
    
    # Remove TUN interface
    remove_tun_interface
    
    # Remove files
    remove_files
    
    # Show summary
    show_summary
    
    print_info "Uninstallation completed successfully!"
}

main
