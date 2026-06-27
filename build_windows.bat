@echo off
REM ============================================================
REM  build_windows.bat - El G POS
REM  Genera dist\ElGV3\ con PyInstaller (ejecutar EN Windows).
REM  Requisitos: Python 3.x instalado y en el PATH.
REM ============================================================
setlocal

echo [1/4] Creando entorno virtual...
if not exist .venv-build (
    python -m venv .venv-build
)
call .venv-build\Scripts\activate.bat

echo [2/4] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo [3/4] Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] Empaquetando con PyInstaller...
pyinstaller ElGV3.spec --noconfirm

echo.
echo ============================================================
echo  Listo. El ejecutable esta en:  dist\ElGV3\ElGV3.exe
echo  Para crear el instalador, abre installer.iss con Inno Setup.
echo ============================================================
pause
