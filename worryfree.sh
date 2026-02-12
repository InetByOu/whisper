#!/bin/bash
# =============================================================================
# worryfree.sh - Hysteria 2 Installer Compatible Ubuntu 24.04 (nftables)
# Versi tanpa warna, syntax bersih, cleanup instalasi lama
# Auth password OPSIONAL - default gstgg47e jika Enter kosong
# Support: Ubuntu 24.04 LTS - Jalankan sebagai root
# =============================================================================

set -e

echo "=== worryfree.sh - Instalasi Hysteria 2 dimulai (Ubuntu 24.04 compatible) ==="
echo "Membersihkan instalasi lama terlebih dahulu..."

# Cleanup instalasi sebelumnya
systemctl stop hysteria-server 2>/dev/null || true
systemctl disable hysteria-server 2>/dev/null || true

rm -f /etc/hysteria/config.yaml
rm -rf /etc/hysteria/*.crt /etc/hysteria/*.key
rm -f /usr/local/bin/hysteria
rm -f /etc/systemd/system/hysteria-server.service
rm -f /etc/nftables.conf

nft flush ruleset 2>/dev/null || true
systemctl restart nftables 2>/dev/null || true

echo "Cleanup selesai. Melanjutkan instalasi baru..."

# Cek OS
if ! grep -qiE 'ubuntu|debian' /etc/os-release; then
    echo "Script ini utama untuk Ubuntu/Debian. Keluar."
    exit 1
fi

# Auto update & upgrade + install deps
echo "Auto update & upgrade paket sistem..."
apt update -y && apt upgrade -y && apt autoremove -y

echo "Install dependencies otomatis (nftables + tools)..."
apt install -y curl wget openssl nftables jq net-tools ca-certificates

# Install Hysteria 2
echo "Install/Upgrade Hysteria 2 official..."
bash <(curl -fsSL https://get.hy2.sh/)

if ! command -v hysteria &> /dev/null; then
    echo "Gagal install Hysteria. Cek koneksi internet."
    exit 1
fi

# Prompt konfigurasi
echo "Masukkan konfigurasi (tekan Enter untuk default):"

read -p "Port listen Hysteria (default: 5667): " HY_PORT
HY_PORT=${HY_PORT:-5667}

read -p "Password auth (default: gstgg47e, tekan Enter untuk default): " AUTH_PASS
if [ -z "$AUTH_PASS" ]; then
    AUTH_PASS="gstgg47e"
    echo "Menggunakan default auth password: gstgg47e"
else
    echo "Menggunakan auth password custom: $AUTH_PASS"
fi

read -p "Obfs salamander password (default: hu``hqb`c): " OBFS_PASS
OBFS_PASS=${OBFS_PASS:-hu``hqb`c}

read -p "SNI / server_name (default: graph.facebook.com): " SNI
SNI=${SNI:-graph.facebook.com}

read -p "Up / Down Mbps (default: 100): " MBPS
MBPS=${MBPS:-100}

# Generate self-signed cert
CERT_DIR="/etc/hysteria"
mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "/CN=$SNI" 2>/dev/null

chmod 600 "$CERT_DIR/server.key"
echo "Self-signed cert dibuat (CN: $SNI)."

# Buat config Hysteria
CONFIG_FILE="/etc/hysteria/config.yaml"

cat > "$CONFIG_FILE" << EOF
listen: :$HY_PORT

tls:
  cert: $CERT_DIR/server.crt
  key: $CERT_DIR/server.key

auth:
  type: password
  password: $AUTH_PASS

bandwidth:
  up: ${MBPS} mbps
  down: ${MBPS} mbps

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

echo "Config Hysteria dibuat di: $CONFIG_FILE"

# Setup nftables
INTERFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
[ -z "$INTERFACE" ] && INTERFACE="eth0"

NFT_CONF="/etc/nftables.conf"

cat > "$NFT_CONF" << EOF
#!/usr/sbin/nft -f

flush ruleset

table inet filter {
    chain input {
        type filter hook input priority 0; policy accept;
        ct state established,related accept
        iif lo accept
        tcp dport 22 accept
        udp dport $HY_PORT accept
        udp dport 3000-19999 accept
    }

    chain forward {
        type filter hook forward priority 0; policy accept;
    }

    chain output {
        type filter hook output priority 0; policy accept;
    }
}

table ip nat {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        udp dport 3000-19999 dnat to :$HY_PORT
    }

    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "$INTERFACE" masquerade
    }
}
EOF

nft -f "$NFT_CONF"
systemctl enable nftables
systemctl restart nftables

echo "nftables setup selesai (DNAT 3000-19999 → $HY_PORT via $INTERFACE)."

# Restart & enable service
systemctl daemon-reload
systemctl restart hysteria-server
systemctl enable hysteria-server --now

sleep 3
if systemctl is-active --quiet hysteria-server; then
    echo "Hysteria 2 service aktif!"
else
    echo "Service gagal start. Cek: journalctl -u hysteria-server -xe"
    exit 1
fi

# Buat URI client
SERVER_IP=$(curl -s ifconfig.me || echo "your-server-ip")
URI="hysteria2://\( {AUTH_PASS}@ \){SERVER_IP}:\( {HY_PORT}/?obfs=salamander&obfs-password= \){OBFS_PASS}&sni=${SNI}&insecure=1"

read -p "Domain kamu (kosongkan jika pakai IP saja): " DOMAIN
if [ -n "$DOMAIN" ]; then
    URI="hysteria2://\( {AUTH_PASS}@ \){DOMAIN}:\( {HY_PORT}/?obfs=salamander&obfs-password= \){OBFS_PASS}&sni=${SNI}&insecure=1"
fi

echo ""
echo "=== Instalasi worryfree.sh Selesai! ==="
echo "Server IP/Domain     : ${DOMAIN:-$SERVER_IP}"
echo "Port internal        : $HY_PORT"
echo "Range hopping client : 3000-19999"
echo "Auth password        : $AUTH_PASS"
echo "Obfs password        : $OBFS_PASS"
echo "SNI                  : $SNI"
echo ""
echo "URI client (copy ke Hiddify/NekoBox):"
echo "$URI"
echo ""
echo "Untuk full hopping: Ganti port di URI jadi :3000-19999"
echo "Cek nftables     : sudo nft list ruleset"
echo "Cek status       : sudo systemctl status hysteria-server"
echo "Cek log          : journalctl -u hysteria-server -e -f"
echo "Semua sudah bersih dan worryfree!"
