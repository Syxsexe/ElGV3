; ============================================================
;  installer.iss - El G POS
;  Inno Setup script para generar el instalador de Windows.
;  1) Ejecuta build_windows.bat (genera dist\ElGV3\).
;  2) Abre este archivo con Inno Setup y pulsa "Compile".
;  Salida: Output\ElGV3-Setup.exe
; ============================================================

#define MyAppName "El G POS"
#define MyAppVersion "3.5"
#define MyAppPublisher "El G"
#define MyAppExeName "ElGV3.exe"

[Setup]
AppId={{B3A1F0E2-7C4D-4E9A-9B12-EL-G-POS-2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\ElGV3
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; La app guarda sus datos en %APPDATA%\ElGV3, no requiere admin para los datos,
; pero instala en Archivos de programa, lo que sí pide elevación.
PrivilegesRequired=admin
OutputDir=Output
OutputBaseFilename=ElGV3-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Descomenta si agregas un icono:
; SetupIconFile=assets\icon.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
; Empaqueta toda la carpeta generada por PyInstaller (onedir).
Source: "dist\ElGV3\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Script de respaldo automático + checklist de puesta en marcha (quedan en {app}).
Source: "registrar_respaldo.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "PUESTA_EN_MARCHA.md";     DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent
