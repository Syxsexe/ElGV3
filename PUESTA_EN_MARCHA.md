# Puesta en marcha — operar YA en modo local (sin DIAN)

Estrategia: **empezar a usar el POS ahora** para poblar la base de datos (productos,
inventario, clientes, ventas, caja) mientras salen los documentos de la DIAN.
Cuando lleguen, se **activa** la facturación electrónica sobre la misma base de datos.

> ✅ **No hay "versión 2".** El programa y la base de datos son los mismos. Activar
> DIAN después es un **cambio de configuración**, no una reinstalación ni una
> migración. Las ventas de esta etapa quedan con numeración local `LOC` (que es lo
> correcto: no se facturan retroactivamente a la DIAN). Las **nuevas** salen ya
> electrónicas. **No se pierde nada.**

Verificado (2026): la app arranca su BD, hace login, registra ventas, persiste y
descuenta stock **sin backend ni DIAN**. Y sin backend configurado **no intenta
sincronizar** (cero latencia; el ticket imprime igual).

---

## ⚠️ Antes de nada — confirmar con tu contador

Que te confirme **qué documento es válido para operar** mientras no estés
habilitado ante la DIAN (tiquete / documento equivalente POS). El sistema imprime
el tiquete; que sea válido fiscalmente en tu caso es una **decisión de tu contador**,
no técnica.

---

## Paso 1 — Generar el instalable (se hace UNA vez, en Windows)

> PyInstaller **no** compila de Linux a Windows. El `.exe` se genera en una
> PC/VM **Windows**. (Si el PC del local NO es Windows, avísame: hay que armar
> otro empaquetado.)

En la máquina Windows, con Python instalado (marcar "Add to PATH") e
[Inno Setup](https://jrsoftware.org/isdl.php):

```bat
build_windows.bat                  REM  -> dist\ElGV3\ElGV3.exe
```
Luego abrir `installer.iss` con Inno Setup → **Compile** → `Output\ElGV3-Setup.exe`.

Detalles en [BUILD.md](BUILD.md).

## Paso 2 — Instalar en el PC del local

1. Ejecutar `ElGV3-Setup.exe` (pide permisos de administrador para instalar).
2. Crea accesos directos en escritorio y menú inicio.
3. Los datos se guardan en `%APPDATA%\ElGV3\` (BD, config, colas) — **fuera** de la
   carpeta del programa, así una actualización no los borra.

## Paso 3 — Primer arranque

1. Abrir la app. En el primer arranque crea la BD y el usuario **admin / admin123**.
2. **Cambiar la contraseña de admin** (módulo Usuarios) y crear usuarios para
   cajeros/vendedores.
3. **NO configurar el backend/DIAN** en el módulo Fiscal todavía → así opera 100%
   local, sin intentos de sincronización.

## Paso 4 — Cargar los datos del negocio

- **Categorías** (tienda / cocina).
- **Productos** con precio y stock inicial. (Insumos y recetas si manejas cocina.)
- **Clientes** frecuentes (opcional).
- **Proveedores** (opcional).
- Abrir **caja** al empezar el día y cerrarla al final.

## Paso 5 — Operar

- Vender normalmente. Cada venta se guarda con numeración local e imprime tiquete.
- La BD se va poblando con el histórico real de ventas, inventario y caja.

## Paso 6 — RESPALDO automático (imprescindible) 💾

La base de datos es la única copia de tus datos. El respaldo está **automatizado**:
la app trae un modo `ElGV3.exe --backup <carpeta>` que hace una copia **consistente
en caliente** (segura aunque la app esté abierta) y rota las copias viejas
(conserva las 30 últimas).

**Registrar la tarea diaria (una sola vez, tras instalar):**

```powershell
.\registrar_respaldo.ps1
```
Opcional, para elegir carpeta y hora:
```powershell
.\registrar_respaldo.ps1 -Destino "D:\RespaldosElG" -Hora "22:30"
```

- Crea una tarea programada de Windows que respalda **todos los días**.
- Por defecto guarda en tu carpeta de **OneDrive** (`Respaldos ElGV3`) → queda
  **fuera del disco del PC**; si el disco falla, no pierdes los datos. Cambia el
  `-Destino` a una USB o carpeta de nube si prefieres.
- Si el PC estaba apagado a esa hora, el respaldo corre en cuanto encienda.

**Probar el respaldo ahora mismo:**
```powershell
Start-ScheduledTask -TaskName "ElGV3 Respaldo diario"
```
Debe aparecer un archivo `elg_pos_AAAAMMDD_HHMMSS.db` en la carpeta destino.

> 💡 Restaurar un respaldo = cerrar la app y copiar el `.db` elegido sobre
> `%APPDATA%\ElGV3\elg_pos.db`.

---

## Cuando lleguen los documentos de la DIAN — activar facturación electrónica

Sin reinstalar y sin perder datos. Yo me encargo de esto; tú traes los documentos:

1. Levantar el **backend local** (ya construido y probado; podman + auto-arranque).
2. Sembrar la **resolución REAL** de la DIAN en la BD del backend.
3. Poner el **token de producción** de Matias y datos del emisor en `backend/.env`.
4. En la app, módulo **Fiscal**: configurar URL del backend + credenciales del POS.
5. A partir de ahí, marcar **"emitir factura electrónica"** en las ventas que lo
   requieran → salen a la DIAN vía el Proveedor Tecnológico.

El plan completo de go-live (fases A–E, trámites DIAN, habilitación) está en el
historial del proyecto; retomamos cuando tengas la resolución y el certificado.
