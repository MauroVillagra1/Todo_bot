# Lee las cuentas de Instagram activas con Instaloader y guarda lo nuevo en la base.
# Lo ejecuta Windows al iniciar sesión (ver scripts/instalar_instagram_local.ps1).
# Registro: %LOCALAPPDATA%\UTNIA\instagram.log
$ErrorActionPreference = "Continue"
$backend = Join-Path (Split-Path $PSScriptRoot -Parent) "backend"
$logDir = Join-Path $env:LOCALAPPDATA "UTNIA"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "instagram.log"

function Escribir($texto) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $texto" | Add-Content $log -Encoding utf8 }

# Al encender la PC la red tarda un poco: se espera hasta 5 minutos
for ($i = 0; $i -lt 30; $i++) {
    try { [System.Net.Dns]::GetHostAddresses("www.instagram.com") | Out-Null; break } catch {}
    Start-Sleep -Seconds 10
}

$env:IG_INSTALOADER = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:ENVIRONMENT = "production"  # sin el eco de SQL de desarrollo
Escribir "Inicio (sesión de Instagram: $(if ($env:IG_SESION) { $env:IG_SESION } else { 'ninguna' }))"
Set-Location $backend
python scripts/run_ingest.py --tipo INSTAGRAM 2>&1 | ForEach-Object { Escribir $_ }
Escribir "Fin (código $LASTEXITCODE)"
