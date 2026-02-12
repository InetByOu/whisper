#!/bin/bash
# update-hysteria2.sh - Hysteria 2 full overwrite updater & fixer
# Selalu ganti file lama dengan yang baru (binary, cert, config, service)
# Professional style: jeda tepat, error handling, clean output

set -e

echo "Starting Hysteria 2 full update (overwrite mode)..."

# 1. Update sistem
echo "[1/10] Updating system packages..."
sudo apt-get update -y >/dev/null 2>&1
sudo apt-get upgrade -y >/dev/null 2>&1
echo "System updated."

sleep 1  # jeda kecil agar output tidak bertabrakan

# 2. Stop & disable service lama
echo "[2/10] Stopping existing Hysteria service..."
systemctl stop hysteria-server >/dev/null 2>&1 || true
systemctl disable hysteria-server >/dev/null 2>&1 || true

# 3. Hapus semua file lama
echo "[3/10] Removing old files..."
rm -f /usr/local/bin/hysteria
rm -rf /etc/hysteria
rm -f /etc/systemd/system/hysteria-server.service

# Flush rules firewall lama
nft flush ruleset >/dev/null 2>&1 || true
iptables -t nat -F >/dev/null 2>&1 || true

echo "Old files removed."

sleep 1

# 4. Download binary Hysteria 2 terbaru
echo "[4/10] Downloading latest Hysteria 2 binary..."
wget -q --show-progress https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 -O /usr/local/bin/hysteria
chmod +x /usr/local/bin/hysteria

echo "Binary updated."

sleep 2  # jeda setelah download besar

# 5. Buat folder config baru
mkdir -p /etc/hysteria

# 6. Generate certificate baru (overwrite)
echo "[5/10] Generating new self-signed certificate..."
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/hysteria/server.key \
    -out /etc/hysteria/server.crt \
    -subj "/CN=graph.facebook.com" >/dev/null 2>&1

chmod 644 /etc/hysteria/server.crt
chmod 644 /etc/hysteria/server.key
chown root:root /etc/hysteria/*

echo "New certificate generated."

sleep 2

# 7. Prompt konfigurasi (aman, tanpa backtick di default)
echo "[6/10] Hysteria 2 Configuration"
DEFAULT_AUTH="gstgg47e"
DEFAULT_OBFS="huhqb_c"   # diubah dari backtick agar aman di Bash
DEFAULT_BW="100"

read -p "Auth password [default: $DEFAULT_AUTH]: " AUTH_PASS
AUTH_PASS=${AUTH_PASS:-$DEFAULT_AUTH}

read -p "Obfs salamander password [default: $DEFAULT_OBFS]: " OBFS_PASS
OBFS_PASS=${OBFS_PASS:-$DEFAULT_OBFS}

read -p "Bandwidth up/down Mbps [default: $DEFAULT_BW]: " BANDWIDTH
BANDWIDTH=${BANDWIDTH:-$DEFAULT_BW}

echo "Configuration received."

sleep 1

# 8. Buat config.yaml baru (overwrite)
echo "[7/10] Creating new config.yaml..."
cat > /etc/hysteria/config.yaml <<EOF
listen: :5667

tls:
  cert: /etc/hysteria/server.crt
  key: /etc/hysteria/server.key

auth:
  type: password
  password: $AUTH_PASS

bandwidth:
  up: ${BANDWIDTH} mbps
  down: ${BANDWIDTH} mbps

obfs:
  type: salamander
  salamander:
    password: "$OBFS_PASS"

masquerade:
  type: proxy
  proxy:
    url: https://www.google.com/
    rewriteHost: true

log:
  level: info
EOF

echo "Config created."

sleep 1

# 9. Buat systemd service baru (overwrite)
echo "[8/10] Creating new systemd service..."
cat <<EOF > /etc/systemd/system/hysteria-server.service
[Unit]
Description=Hysteria 2 Server
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/hysteria server -c /etc/hysteria/config.yaml
Restart=always
RestartSec=3
Environment=HYSTERIA_LOG_LEVEL=info
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

# 10. Set capability & reload
setcap cap_net_bind_service=+ep /usr/local/bin/hysteria >/dev/null 2>&1 || true
systemctl daemon-reload

# 11. Start & enable service
echo "[9/10] Starting Hysteria 2 service..."
systemctl enable hysteria-server >/dev/null 2>&1
systemctl restart hysteria-server

sleep 5   # jeda penting agar service benar-benar start

# 12. Re-apply DNAT & firewall
echo "[10/10] Applying DNAT & firewall rules..."
IFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
[ -z "$IFACE" ] && IFACE="eth0"

iptables -t nat -D PREROUTING -i "$IFACE" -p udp --dport 3000:19999 -j DNAT --to-destination :5667 2>/dev/null || true
iptables -t nat -A PREROUTING -i "$IFACE" -p udp --dport 3000:19999 -j DNAT --to-destination :5667

ufw allow 5667/udp >/dev/null 2>&1 || true
ufw allow 3000:19999/udp >/dev/null 2>&1 || true
ufw reload >/dev/null 2>&1 || true

# 13. Cek hasil
echo ""
echo "=== Hysteria 2 update completed ==="
systemctl status hysteria-server -l

echo ""
echo "Last 20 log lines:"
journalctl -u hysteria-server -n 20 --no-pager

echo ""
echo "Server IP: $(curl -s ifconfig.me)"
echo "Internal port: 5667"
echo "Hopping range: 3000-19999"
echo "Auth: $AUTH_PASS"
echo "Obfs: $OBFS_PASS"
echo ""
echo "URI hopping example:"
echo "hysteria2://\( AUTH_PASS@ \)(curl -s ifconfig.me):3000-19999/?obfs=salamander&obfs-password=$OBFS_PASS&sni=graph.facebook.com&insecure=1"
echo ""
echo "Done! If service still failed, paste the status output above."
