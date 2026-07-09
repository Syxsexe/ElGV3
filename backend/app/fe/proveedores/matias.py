"""
Adaptador de Matias API (Proveedor Tecnológico DIAN).

Modelo "datos → el PT hace todo": enviamos JSON a POST /documents y Matias genera
el XML UBL, el CUFE, firma con el certificado (cargado en Matias) y transmite a
DIAN. La validación DIAN es asíncrona (30 min – 2 h); el veredicto final llega
por webhook (`document.accepted` / `document.rejected`) y, como respaldo, por
consulta a GET /invoices/{prefix}-{numero}.

Docs: https://docs.matias-api.com
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from config import settings
from app.fe.base import (
    ProveedorFE, DocumentoFE, ResultadoFE, EventoWebhook, Estado,
)
from app.fe.proveedores.matias_mapper import construir_payload

logger = logging.getLogger(__name__)


def _es_verdadero(v: Any) -> bool:
    """Normaliza el is_valid de Matias (1/'1'/True/'true') a bool."""
    return str(v).strip().lower() in ("1", "true", "t", "yes")


# StatusCode DIAN → estado interno.
def _estado_por_status_code(code: str | None) -> Estado:
    if code == "00":
        return "aceptada"
    if code == "98":
        return "en_proceso"
    return "rechazada"


# Evento de webhook → estado interno.
_EVENTO_ESTADO: dict[str, Estado] = {
    "document.accepted": "aceptada",
    "document.rejected": "rechazada",
    "document.voided": "anulada",
    "document.emitted": "en_proceso",
    "document.created": "en_proceso",
}


# Ruta de emisión según tipo de documento (base .../api/ubl2.1).
_RUTA_EMISION: dict[str, str] = {
    "factura": "/invoice",
    "nota_credito": "/notes/credit",
    "nota_debito": "/notes/debit",
}


class MatiasProvider(ProveedorFE):
    nombre = "matias"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        email: str | None = None,
        password: str | None = None,
        webhook_secret: str | None = None,
        generar_pdf: bool | None = None,
        enviar_email: bool | None = None,
        force_status: str | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or settings.matias_base_url).rstrip("/")
        self.token = token if token is not None else settings.matias_token
        self.email = email if email is not None else settings.matias_email
        self.password = password if password is not None else settings.matias_password
        self.webhook_secret = (
            webhook_secret if webhook_secret is not None else settings.matias_webhook_secret
        )
        self.generar_pdf = settings.matias_generar_pdf if generar_pdf is None else generar_pdf
        self.enviar_email = settings.matias_enviar_email if enviar_email is None else enviar_email
        self.force_status = (
            force_status if force_status is not None else settings.matias_force_status
        )
        self.timeout = timeout or settings.matias_timeout
        self._access_token: str | None = None  # cache del login (si aplica)

    # ── Autenticación ─────────────────────────────────────────────────────────
    async def _get_token(self, client: httpx.AsyncClient) -> str | None:
        """Devuelve el Bearer a usar: PAT si está configurado, si no hace login."""
        if self.token:
            return self.token
        if self._access_token:
            return self._access_token
        if not (self.email and self.password):
            return None
        resp = await client.post(
            f"{self.base_url}/auth/login",
            json={"email": self.email, "password": self.password, "remember_me": 0},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if resp.status_code >= 400:
            logger.error("Login Matias falló: HTTP %s", resp.status_code)
            return None
        self._access_token = resp.json().get("access_token")
        return self._access_token

    def _headers(self, token: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Sólo tiene efecto en sandbox; producción lo ignora.
        if self.force_status:
            headers["X-Sandbox-Force-Status"] = self.force_status
        return headers

    # ── Emisión ──────────────────────────────────────────────────────────────
    async def emitir(self, doc: DocumentoFE) -> ResultadoFE:
        ruta = _RUTA_EMISION.get(doc.tipo)
        if ruta is None:
            return ResultadoFE(estado="error", numero=doc.numero,
                               mensaje=f"Tipo de documento no soportado: {doc.tipo}")

        payload = construir_payload(
            doc, generar_pdf=self.generar_pdf, enviar_email=self.enviar_email
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                token = await self._get_token(client)
                if not token:
                    return ResultadoFE(
                        estado="error", numero=doc.numero,
                        mensaje="Sin credenciales Matias (MATIAS_TOKEN o email/password)",
                    )
                resp = await client.post(
                    f"{self.base_url}{ruta}",
                    json=payload,
                    headers=self._headers(token),
                )
        except httpx.RequestError as e:
            logger.error("Error de red hacia Matias: %s", e)
            return ResultadoFE(
                estado="error", numero=doc.numero,
                mensaje=f"Error de conexión con Matias: {e}",
            )

        resultado = self._parse_documento(resp, numero_defecto=doc.numero)

        # El PT puede devolver 5xx DESPUÉS de haber creado y validado el
        # documento (p.ej. un crash en su generación del PDF). Reintentar el
        # POST duplicaría la factura (consume consecutivo DIAN), así que
        # confirmamos por consulta de estado antes de darla por perdida.
        if resultado.estado == "error" and resp.status_code >= 500:
            verificado = await self.consultar_estado(
                prefijo=doc.prefijo, consecutivo=doc.consecutivo
            )
            if verificado.cufe:
                logger.warning(
                    "POST %s devolvió HTTP %s pero el documento %s SÍ se creó "
                    "(CUFE %s); uso el estado consultado.",
                    ruta, resp.status_code, doc.numero, verificado.cufe,
                )
                return verificado

        return resultado

    # ── Consulta de estado (respaldo del webhook) ────────────────────────────
    async def consultar_estado(
        self, *, prefijo: str, consecutivo: int, track_id: str | None = None
    ) -> ResultadoFE:
        numero = f"{prefijo}{consecutivo}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                token = await self._get_token(client)
                if not token:
                    return ResultadoFE(estado="error", numero=numero,
                                       mensaje="Sin credenciales Matias")
                # Consulta por prefijo+número (verificada). NOTA: la ruta
                # /status/document/{track_id} devuelve 405 en la API real, así
                # que no se usa; el track_id se conserva sólo por compatibilidad.
                resp = await client.get(
                    f"{self.base_url}/status",
                    params={"prefix": prefijo, "number": f"{prefijo}{consecutivo}"},
                    headers=self._headers(token),
                )
        except httpx.RequestError as e:
            return ResultadoFE(
                estado="error", numero=numero,
                mensaje=f"Error consultando estado en Matias: {e}",
            )
        return self._parse_status_document(resp, numero_defecto=numero)

    def _parse_documento(self, resp: httpx.Response, *, numero_defecto: str) -> ResultadoFE:
        raw: dict[str, Any]
        try:
            raw = resp.json()
        except (json.JSONDecodeError, ValueError):
            raw = {"raw_text": resp.text}

        if resp.status_code >= 400:
            return ResultadoFE(
                estado="error",
                numero=numero_defecto,
                mensaje=f"HTTP {resp.status_code}: {raw.get('message') or resp.text[:300]}",
                raw=raw,
            )

        dian = raw.get("response") or {}
        status_code = dian.get("StatusCode")
        estado = _estado_por_status_code(status_code)

        # success=false sin rechazo explícito de DIAN → error técnico.
        if raw.get("success") is False and status_code is None:
            estado = "error"

        mensaje = (
            dian.get("StatusMessage")
            or dian.get("StatusDescription")
            or raw.get("message")
        )
        # Errores de reglas DIAN cuando hay rechazo.
        if estado == "rechazada":
            errores = (dian.get("ErrorMessage") or {}).get("string")
            if errores:
                mensaje = "; ".join(errores) if isinstance(errores, list) else str(errores)

        qr = raw.get("qr") or {}
        pdf = raw.get("pdf") or {}
        adjunto = raw.get("AttachedDocument") or {}

        return ResultadoFE(
            estado=estado,
            cufe=raw.get("XmlDocumentKey") or dian.get("XmlDocumentKey"),
            track_id=str(raw.get("document_id")) if raw.get("document_id") else None,
            numero=numero_defecto,
            qr=qr.get("url") or qr.get("qrDian") or None,
            pdf_url=pdf.get("url") or None,
            xml_url=adjunto.get("url") or None,
            mensaje=mensaje,
            raw=raw,
        )

    def _parse_status_document(self, resp: httpx.Response, *, numero_defecto: str) -> ResultadoFE:
        """Parsea GET /status, cuya forma es {document:{...}, status, success}
        (distinta a la de emisión). Se usa en la consulta de estado y en el
        respaldo de `emitir` cuando el POST devuelve 5xx."""
        try:
            raw = resp.json()
        except (json.JSONDecodeError, ValueError):
            raw = {"raw_text": resp.text}

        if resp.status_code >= 400:
            return ResultadoFE(
                estado="error", numero=numero_defecto,
                mensaje=f"HTTP {resp.status_code}: {raw.get('message') or resp.text[:300]}",
                raw=raw,
            )

        doc = raw.get("document") or {}
        if not doc:
            return ResultadoFE(
                estado="error", numero=numero_defecto,
                mensaje=raw.get("message") or "Documento no encontrado", raw=raw,
            )

        texto_estado = (raw.get("status") or "").lower()
        if "rechaz" in texto_estado or "reject" in texto_estado:
            estado: Estado = "rechazada"
        elif doc.get("is_valid"):
            estado = "aceptada"
        else:
            # Existe pero DIAN aún no lo valida (validación asíncrona 30 min–2 h).
            estado = "en_proceso"

        qr = doc.get("qr") or {}
        return ResultadoFE(
            estado=estado,
            cufe=doc.get("document_key"),
            track_id=str(doc.get("uuid")) if doc.get("uuid") else None,
            numero=doc.get("document_number") or numero_defecto,
            qr=qr.get("qrDian") or qr.get("url") or None,
            mensaje=raw.get("status") or raw.get("message"),
            raw=raw,
        )

    # ── Chequeo de conexión (solo lectura) ───────────────────────────────────
    async def verificar_conexion(self) -> dict[str, Any]:
        """GET /tokens (read-only) para validar token + base. No emite nada."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                token = await self._get_token(client)
                if not token:
                    return {"ok": False, "status": None, "base_url": self.base_url,
                            "mensaje": "Sin credenciales Matias (MATIAS_TOKEN o email/password)"}
                resp = await client.get(
                    f"{self.base_url}/tokens", headers=self._headers(token)
                )
        except httpx.RequestError as e:
            return {"ok": False, "status": None, "base_url": self.base_url,
                    "mensaje": f"Error de conexión: {e}"}
        ok = resp.status_code == 200
        return {
            "ok": ok,
            "status": resp.status_code,
            "base_url": self.base_url,
            "mensaje": "Conexión OK" if ok else f"Respuesta inesperada HTTP {resp.status_code}",
        }

    # ── Webhook ──────────────────────────────────────────────────────────────
    def verificar_firma_webhook(self, body: bytes, firma: str | None) -> bool:
        if not self.webhook_secret or not firma:
            return False
        # Matias/APIDIAN firma el JSON COMPACTO (sin espacios) del cuerpo, NO los
        # bytes crudos que envía (verificado con un webhook real). Probamos varias
        # serializaciones y aceptamos si alguna coincide; al ser HMAC, sin el secret
        # no se puede forjar ninguna. El header puede venir como "sha256=<hex>".
        recibido = (firma.split("=", 1)[1] if "=" in firma else firma).strip().lower()
        candidatos: list[bytes] = [body]
        try:
            obj = json.loads(body)
            candidatos.append(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
            candidatos.append(json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass
        clave = self.webhook_secret.encode("utf-8")
        for cand in candidatos:
            esperado = hmac.new(clave, cand, hashlib.sha256).hexdigest()
            if hmac.compare_digest(esperado, recibido):
                return True
        return False

    def parse_webhook(self, payload: dict[str, Any]) -> EventoWebhook:
        # Formato real Matias/APIDIAN v3 (verificado con webhook capturado):
        # el tipo va en `type` (también en header X-Webhook-Event) y el
        # identificador de seguimiento del documento es `data.uuid`.
        evento = payload.get("type") or payload.get("event") or ""
        data = payload.get("data") or {}
        track_id = (
            data.get("uuid")
            or data.get("track_id")
            or (str(data.get("document_id")) if data.get("document_id") is not None else None)
        )
        # Estado: rechazo/anulación mandan; si no, `is_valid` es la señal real
        # (en sandbox llega 1 de inmediato; en producción 0 hasta que DIAN valide).
        if evento == "document.rejected":
            estado: Estado = "rechazada"
        elif evento == "document.voided":
            estado = "anulada"
        elif _es_verdadero(data.get("is_valid")):
            estado = "aceptada"
        else:
            estado = _EVENTO_ESTADO.get(evento, "en_proceso")
        return EventoWebhook(
            evento=evento,
            estado=estado,
            track_id=track_id,
            cufe=data.get("cufe") or data.get("XmlDocumentKey"),
            numero=data.get("document_number") or data.get("number"),
            mensaje=data.get("status_message") or data.get("message") or evento,
            raw=payload,
        )
