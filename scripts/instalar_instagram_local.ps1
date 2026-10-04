# Configura la lectura de Instagram al iniciar Windows (una sola vez).
#
# Uso (PowerShell, desde la raíz del repo):
#   instaloader --login TU_USUARIO          # pide la contraseña y guarda la sesión
#   .\scripts\instalar_instagram_local.ps1 -Usuario TU_USUARIO
#
# Crea un acceso directo en la carpeta Inicio de Windows que corre
# scripts/instagram_local.ps1 oculto. Para desactivarlo, borrar
# "UTNIA Instagram.lnk" de shell:startup.
param([Parameter(Mandatory = $true)][string]$Usuario)

[Environment]::SetEnvironmentVariable("IG_SESION", $Usuario, "User")

$script = Join-Path $PSScriptRoot "instagram_local.ps1"
$inicio = [Environment]::GetFolderPath("Startup")
$acceso = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $inicio "UTNIA Instagram.lnk"))
$pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
$acceso.TargetPath = if ($pwsh) { $pwsh.Source } else { "powershell.exe" }
$acceso.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$acceso.WindowStyle = 7  # minimizada
$acceso.Save()

Write-Host "Listo: se ejecuta al iniciar sesión en Windows con la cuenta '$Usuario'."
Write-Host "Registro: $env:LOCALAPPDATA\UTNIA\instagram.log"
