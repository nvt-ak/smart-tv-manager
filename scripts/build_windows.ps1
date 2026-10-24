# Build TV Remote Hub for Windows (run in PowerShell on a Windows PC).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

if (-not (Test-Path "assets\app-icon.ico")) {
    Write-Host "Generating app-icon.ico..."
    python -m pip install pillow -q
    python -c "from PIL import Image; img=Image.open('ui/assets/app-icon-1024.png').convert('RGBA'); img.save('assets/app-icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
}

python -m pip install -r requirements.txt -r requirements-build.txt
pyinstaller tv_remote_hub.spec --noconfirm --clean

$out = Join-Path (Get-Location) "dist\TVRemoteHub"
Write-Host ""
Write-Host "Build OK: $out\TVRemoteHub.exe"
Write-Host "Zip the whole TVRemoteHub folder to distribute (WebView2 runtime must be on the PC)."
