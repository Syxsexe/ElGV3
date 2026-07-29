<#
    registrar_respaldo.ps1 — El G POS
    Registra una TAREA PROGRAMADA de Windows que respalda la base de datos
    todos los días, llamando al propio ejecutable: ElGV3.exe --backup <carpeta>.

    Uso (una sola vez, tras instalar la app):
        - Click derecho sobre este archivo -> "Ejecutar con PowerShell", o
        - En PowerShell:  .\registrar_respaldo.ps1
        - Para elegir carpeta/hora:
              .\registrar_respaldo.ps1 -Destino "D:\RespaldosElG" -Hora "22:30"

    Recomendado: que -Destino sea una carpeta de NUBE (OneDrive/Drive) o una USB,
    para que la copia quede FUERA del disco del PC (si el disco falla, no la pierdes).
#>
param(
    [string]$Destino = "",
    [string]$Hora    = "22:00",
    [string]$Nombre  = "ElGV3 Respaldo diario"
)

$ErrorActionPreference = "Stop"

# 1) Localizar el ejecutable instalado.
$exe = Join-Path $env:ProgramFiles "ElGV3\ElGV3.exe"
if (-not (Test-Path $exe)) { $exe = Join-Path ${env:ProgramFiles(x86)} "ElGV3\ElGV3.exe" }
if (-not (Test-Path $exe)) { $exe = Join-Path $env:LOCALAPPDATA "Programs\ElGV3\ElGV3.exe" }
if (-not (Test-Path $exe)) {
    Write-Error "No encuentro ElGV3.exe. Instala la app primero (ElGV3-Setup.exe)."
    exit 1
}

# 2) Carpeta destino por defecto: OneDrive si existe (queda fuera del disco), si no el perfil.
if ([string]::IsNullOrWhiteSpace($Destino)) {
    if (-not [string]::IsNullOrWhiteSpace($env:OneDrive)) {
        $Destino = Join-Path $env:OneDrive "Respaldos ElGV3"
    } else {
        $Destino = Join-Path $env:USERPROFILE "Respaldos ElGV3"
    }
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# 3) Registrar la tarea (diaria, a la hora indicada; corre cuando el usuario tiene sesión).
$accion     = New-ScheduledTaskAction -Execute $exe -Argument "--backup `"$Destino`""
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
# StartWhenAvailable: si el PC estaba apagado a esa hora, corre en cuanto encienda.
$ajustes    = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador `
    -Settings $ajustes -Description "Respaldo diario de la base de datos de El G POS" -Force | Out-Null

Write-Host ""
Write-Host "OK - Tarea programada creada:" -ForegroundColor Green
Write-Host "     Nombre : $Nombre"
Write-Host "     Cuando : todos los dias a las $Hora"
Write-Host "     Copia  : $exe --backup"
Write-Host "     Destino: $Destino"
Write-Host ""
Write-Host "Probar ahora (genera un respaldo inmediato):"
Write-Host "     Start-ScheduledTask -TaskName `"$Nombre`""
Write-Host "Se ve tambien en el Programador de tareas de Windows -> Biblioteca."
Write-Host "Quitar la tarea:"
Write-Host "     Unregister-ScheduledTask -TaskName `"$Nombre`" -Confirm:`$false"
