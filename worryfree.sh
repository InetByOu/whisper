#!/bin/bash
# update-hysteria2.sh - Hysteria 2 updater profesional (overwrite full + fix backtick)
# Selalu ganti file lama dengan baru, tanpa backtick di default password

set -e

echo "Mulai update Hysteria 2 (mode overwrite total)..."

# 1. Update sistem
echo "[1/11] Update paket sistem..."
sudo apt-get update -y >/dev/null 2>&1
sudo apt-get upgrade -y >/dev/null 2>&1
echo "Sistem sudah update."

sleep 1

# 2. Stop & hapus service lama
echo "[2/11] Stop dan hapus service lama..."
systemctl stop hysteria-server >/dev/null 2>&1 || true
systemctl disable hysteria-server >/dev/null 2>&1 || true

# 3. Hapus semua file lama
echo "[3/11] Hapus file lama..."
rm -f /usr/local/bin/hysteria
rm -rf /etc/hysteria
rm -f /etc/systemd/system/hysteria-server.service

nft flush ruleset >/dev/null 2>&1 || true
iptables -t nat -F >/dev/null 2>&1 || true

echo "File lama dihapus."

sleep 1

# 4. Download binary terbaru
echo "[4/11] Download Hysteria 2 versi terbaru..."
wget -q --show-progress https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 -O /usr/local/bin/hysteria
chmod +x /usr/local/bin/hysteria

echo "Binary di-update."

sleep 2

# 5. Buat folder config
mkdir -p /etc/hysteria

# 6. Generate cert baru
echo "[5/11] Generate sertifikat self-signed baru..."
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/hysteria/server.key \
    -out /etc/hysteria/server.crt \
    -subj "/CN=graph.facebook.com" >/dev/null 2>&1

chmod 644 /etc/hysteria/server.crt
chmod 644 /etc/hysteria/server.key
chown root:root /etc/hysteria/*

echo "Sertifikat baru selesai."

sleep 2

# 7. Prompt konfigurasi (password obfs tanpa backtick)
echo "[6/11] Konfigurasi Hysteria 2"
DEFAULT_AUTH="gstgg47e"
DEFAULT_OBFS="huhqb_c"     # aman, tanpa backtick
DEFAULT_BW="100"

read -p "Password auth [default: $DEFAULT_AUTH]: " AUTH_PASS
AUTH_PASS=${AUTH_PASS:-$DEFAULT_AUTH}

read -p "Password obfs salamander [default: $DEFAULT_OBFS]: " OBFS_PASS
OBFS_PASS=${OBFS_PASS:-$DEFAULT_OBFS}

read -p "Bandwidth up/down Mbps [default: $DEFAULT_BW]: " BANDWIDTH
BANDWIDTH=${BANDWIDTH:-$DEFAULT_BW}

echo "Konfigurasi diterima."

sleep 1

# 8. Buat config.yaml baru
echo "[7/11] Buat config.yaml baru..."
cat > /etc/hysteria/config.yaml <<'EOF'
listen: :5667

tls:
  cert: /etc/hysteria/server.crt
  key: /etc/hysteria/server.key

auth:
  type: password
  password: '"$AUTH_PASS"'

bandwidth:
  up: '"${BANDWIDTH}"' mbps
  down: '"${BANDWIDTH}"' mbps

obfs:
  type: salamander
  salamander:
    password: '"$OBFS_PASS"'

masquerade:
  type: proxy
  proxy:
    url: https://www.google.com/
    rewriteHost: true

log:
  level: info
EOF

echo "Config.yaml baru dibuat."

sleep 1

# 9. Buat service file baru
echo "[8/11] Buat file systemd service baru..."
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

# 11. Start service
echo "[9/11] Start ulang service..."
systemctl enable hysteria-server >/dev/null 2>&1
systemctl restart hysteria-server

sleep 8   # jeda lebih panjang untuk memastikan start

# 12. Apply firewall & DNAT
echo "[10/11] Apply firewall & DNAT hopping..."
IFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
[ -z "$IFACE" ] && IFACE="eth0"

iptables -t nat -D PREROUTING -i "$IFACE" -p udp --dport 3000:19999 -j DNAT --to-destination :5667 2>/dev/null || true
iptables -t nat -A PREROUTING -i "$IFACE" -p udp --dport 3000:19999 -j DNAT --to-destination :5667

ufw allow 5667/udp >/dev/null 2>&1 || true
ufw allow 3000:19999/udp >/dev/null 2>&1 || true
ufw reload >/dev/null 2>&1 || true

# 13. Verifikasi
echo "[11/11] Verifikasi akhir..."
sleep 2

echo "=== Status service ==="
systemctl status hysteria-server -l

echo ""
echo "=== Log terakhir (20 baris) ==="
journalctl -u hysteria-server -n 20 --no-pager

echo ""
echo "Update selesai! Jika service active (running), server sudah OK."
echo "IP server: $(curl -s ifconfig.me)"
echo "Port internal: 5667"
echo "Range hopping: 3000-19999"
echo "Auth: $AUTH_PASS"
echo "Obfs: $OBFS_PASS"
echo ""
echo "URI contoh hopping:"
echo "hysteria2://\( AUTH_PASS@ \)(curl -s ifconfig.me):3000-19999/?obfs=salamander&obfs-password=$OBFS_PASS&sni=graph.facebook.com&insecure=1"
echo ""
echo "Jika masih error, paste output status & log di atas."
