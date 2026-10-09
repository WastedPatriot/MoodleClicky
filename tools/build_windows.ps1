# Build MoodleClicky for Windows -> dist\MoodleClicky\MoodleClicky.exe and dist\MoodleClicky-windows.zip
# Then runs the built exe's self-test (fails the build if anything is broken).
#   powershell -ExecutionPolicy Bypass -File tools\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

python -m pip install --upgrade pip | Out-Null
python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

python tools\make_icon.py

pyinstaller --noconfirm --clean --windowed --onedir --name MoodleClicky `
  --icon build\moodleclicky.ico `
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all onnxruntime --collect-all tokenizers `
  --collect-data soundcard --collect-submodules pystray --collect-submodules pynput `
  --hidden-import keyring.backends.Windows --collect-binaries av `
  moodleclicky\__main__.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = "dist\MoodleClicky\MoodleClicky.exe"
$report = Join-Path (Resolve-Path dist) "selftest.txt"
$p = Start-Process -FilePath $exe -ArgumentList "--selftest", "`"$report`"", "--with-model" -Wait -PassThru
Get-Content $report
if ($p.ExitCode -ne 0) { throw "Self-test of the built exe FAILED (exit $($p.ExitCode))" }

Copy-Item README.md, LICENSE dist\MoodleClicky\
Compress-Archive -Path dist\MoodleClicky -DestinationPath dist\MoodleClicky-windows.zip -Force
Write-Host "Built dist\MoodleClicky-windows.zip"
