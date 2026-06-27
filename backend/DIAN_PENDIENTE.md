# DIAN — Pendientes para producción

Estado actual: la integración funciona en **mock** y la infraestructura (login POS,
transmisión, `TestSetId` parametrizable) está lista. Falta lo que depende de datos
y trámites con la **DIAN**, que aún no se han obtenido.

## 1. Datos a solicitar a la DIAN
Al habilitarte como facturador electrónico, la DIAN entrega:

- [ ] **SoftwareID** — identificador del software autorizado.
- [ ] **PIN / SoftwareSecurityCode** — clave del software.
- [ ] **TestSetId** — identificador del juego de pruebas (set de habilitación).
- [ ] **Clave técnica** de cada **resolución de numeración** (prefijo + rango).
- [ ] **Certificado digital `.p12`** (ONAC) + su contraseña.

Una vez obtenidos, cargarlos en:
- `.env`: `DIAN_SOFTWARE_ID`, `DIAN_SOFTWARE_PIN`, `DIAN_TEST_SET_ID`.
- Panel admin: certificado (`/admin/certificado`) y resoluciones (`/admin/resoluciones`).

## 2. Trabajo de código pendiente (cuando se tengan los datos)
Estos valores ya tienen su config, pero **todavía no se usan en el XML**:

- [ ] Emitir `SoftwareID` y `SoftwareSecurityCode` en la extensión UBL
      (`SoftwareProvider`) del XML — falta en `backend/app/dian/xml_generator.py`
      y `xml_dee_pos.py`.
- [ ] **Revisar la fórmula del CUFE** (`backend/app/dian/cufe.py`): la actual está
      simplificada. La oficial incluye los códigos y valores de cada impuesto y el
      tipo de ambiente. Validar contra el **anexo técnico DIAN** vigente.
- [ ] Probar el flujo completo en ambiente **test** (vpfe-hab) con el juego de
      pruebas antes de pasar a **prod**.

## Progresión de ambientes
```
mock  →  test (habilitación, vpfe-hab)  →  prod (vpfe)
```
Se controla con `DIAN_ENVIRONMENT` en el `.env`.
