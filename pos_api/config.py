"""
pos_api/config.py — El G POS (servicio web, piloto Ventas/Cuentas)

Configuración vía variables de entorno. Nada de esto se comparte con
backend/ (integración DIAN) — este es un servicio separado.
"""
import os

# Clave para firmar los JWT de sesión de vendedor. En producción se debe fijar
# con la variable de entorno ELG_JWT_SECRET (ej. en el .env del servidor).
JWT_SECRET = os.environ.get("ELG_JWT_SECRET", "dev-secret-cambiar-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HORAS = int(os.environ.get("ELG_JWT_EXP_HORAS", "12"))

# Orígenes permitidos para CORS (el front web servido desde la LAN). Por
# defecto solo localhost; en el servidor real se fija a la IP/hostname del
# server dentro de la subred local, nunca "*".
CORS_ORIGINS = os.environ.get(
    "ELG_CORS_ORIGINS", "http://localhost:5173"
).split(",")
