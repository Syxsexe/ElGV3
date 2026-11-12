#!/usr/bin/env bash
# Crea el remoto cifrado "elg-drive" de rclone (donde respaldo.sh sube las
# copias), encima del remoto "gdrive" ya autorizado. Pide las contraseñas sin
# mostrarlas; guárdalas fuera del servidor: sin ellas los respaldos de Drive
# no se pueden abrir.
#   ~/elg/configurar-drive.sh
set -euo pipefail

if ! rclone listremotes | grep -qx 'gdrive:'; then
    echo "Primero autoriza Google Drive: rclone config create gdrive drive scope=drive.file" >&2
    exit 1
fi
if rclone listremotes | grep -qx 'elg-drive:'; then
    read -r -p "Ya existe elg-drive. ¿Reemplazarlo? Los respaldos ya subidos solo se abren con las contraseñas viejas [s/N]: " si
    [[ "$si" == [sS] ]] || exit 0
fi

pedir() {
    local a b
    while true; do
        read -r -s -p "$1 (mínimo 12 caracteres): " a; echo >&2
        read -r -s -p "Repítela: " b; echo >&2
        if [[ "$a" != "$b" ]]; then echo "No coinciden, otra vez." >&2
        elif (( ${#a} < 12 )); then echo "Muy corta, otra vez." >&2
        else printf '%s' "$a"; return
        fi
    done
}

clave=$(pedir "Contraseña de cifrado")
sal=$(pedir "Segunda contraseña (sal), distinta de la primera")
if [[ "$clave" == "$sal" ]]; then
    echo "Las dos contraseñas deben ser distintas." >&2
    exit 1
fi

rclone config create elg-drive crypt remote=gdrive:elg-pos \
    filename_encryption=standard directory_name_encryption=true \
    password="$clave" password2="$sal" --obscure >/dev/null
chmod 600 "$(rclone config file | tail -n1)"

# Prueba: subir, leer y borrar un archivo.
echo "prueba $(date)" | rclone rcat elg-drive:prueba.txt
rclone cat elg-drive:prueba.txt >/dev/null
rclone deletefile elg-drive:prueba.txt
echo "✓ elg-drive listo: los respaldos se suben cifrados a la carpeta elg-pos de tu Drive."
echo "  Guarda las dos contraseñas en un lugar seguro fuera del servidor."
