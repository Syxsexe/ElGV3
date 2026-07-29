# Generar el ejecutable e instalador (Windows)

> ⚠️ PyInstaller **no** compila desde Linux a Windows. Estos pasos se ejecutan
> en una PC/VM **Windows**.

## Requisitos en la máquina Windows
- **Python 3.12 de 64 bits** (recomendado; marcar "Add Python to PATH" al instalar).
  Evita el 3.14 recién salido: algunas dependencias aún no traen *wheels* para él y
  el build puede fallar al instalar. 3.12 es un piso probado y estable.
- [Inno Setup](https://jrsoftware.org/isdl.php) (para el instalador).

## 1. Generar el ejecutable
Desde la carpeta del proyecto, en `cmd`:

```bat
build_windows.bat
```

Esto crea un entorno virtual, instala dependencias y empaqueta con PyInstaller.
Resultado: `dist\ElGV3\ElGV3.exe` (carpeta autónoma, modo *onedir*).

Para probarlo, ejecuta ese `.exe` directamente.

## 2. Generar el instalador
1. Abre `installer.iss` con **Inno Setup**.
2. Pulsa **Compile** (▶).
3. Salida: `Output\ElGV3-Setup.exe`.

El instalador crea accesos directos (escritorio + menú inicio) y un desinstalador.

## Dónde se guardan los datos
La app empaquetada guarda la base de datos y la configuración en:

```
%APPDATA%\ElGV3\
  elg_pos.db          (base de datos)
  config.json         (tema, preferencias)
  dian_config.json    (credenciales DIAN — opcional)
  sync_queue.json     (cola de sincronización)
```

En la **primera ejecución** se crea la base de datos con un usuario admin por
defecto: **admin / admin123** (cámbialo desde el módulo Usuarios).

## Personalizar el icono (opcional)
Coloca un `assets\icon.ico` y descomenta la línea `SetupIconFile` en
`installer.iss`. El `.spec` lo detecta automáticamente.

## Notas
- La impresión directa de tickets (`win32print`) solo funciona en Windows.
- El `backend/` (servicio cloud DIAN) **no** se empaqueta; es independiente.
