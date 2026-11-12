#!/usr/bin/env bash
# Lo que necesita root, una sola vez: que podman sin root pueda usar el
# puerto 80 y abrirlo en el firewall a las redes privadas y a Tailscale.
#   sudo ./preparar-root.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Córrelo con sudo." >&2; exit 1; }

echo 'net.ipv4.ip_unprivileged_port_start=80' >/etc/sysctl.d/60-elg-puerto80.conf
sysctl -q --system

if command -v ufw >/dev/null; then
    for red in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10; do
        ufw allow from "$red" to any port 80 proto tcp comment 'El G POS' >/dev/null
    done
    ufw status | grep -E '^80/tcp' || true
fi
echo "Listo: puerto 80 disponible para el usuario y abierto a la red local."
