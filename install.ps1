# MoodleClicky installer / updater / setup menu / uninstaller (Windows PowerShell 5.1+ or PowerShell 7).
#
#   Install or update (paste into PowerShell):
#     irm https://raw.githubusercontent.com/WastedPatriot/moodleclicky/main/install.ps1 | iex
#   Re-run just the setup menu:   Start menu -> "MoodleClicky Setup"
#   Uninstall:                    Start menu -> "Uninstall MoodleClicky"
#
# Installs to %LOCALAPPDATA%\Programs\MoodleClicky (no admin needed). Your settings, notes and lecture
# transcripts live in %APPDATA%\MoodleClicky and are kept across updates.
param(
    [switch]$Setup,      # only show the setup menu
    [switch]$Uninstall,
    [string]$Zip = ""    # install from a local MoodleClicky-windows.zip instead of downloading
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # makes downloads much faster on Windows PowerShell
$Repo = "WastedPatriot/moodleclicky"
$Dir = Join-Path $env:LOCALAPPDATA "Programs\MoodleClicky"
$Exe = Join-Path $Dir "MoodleClicky.exe"
$Data = Join-Path $env:APPDATA "MoodleClicky"
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$Desktop = [Environment]::GetFolderPath("Desktop")
$RawScript = "https://raw.githubusercontent.com/$Repo/main/install.ps1"

function Say($text, $color = "Gray") { Write-Host $text -ForegroundColor $color }
function Step($text) { Write-Host ""; Write-Host "  > $text" -ForegroundColor Cyan }
function Banner {
    Clear-Host
    Say ""
    Say "   __  __                 _ _       ____ _ _      _          " Blue
    Say "  |  \/  | ___   ___   __| | | ___ / ___| (_) ___| | ___   _ " Blue
    Say "  | |\/| |/ _ \ / _ \ / _`` | |/ _ \ |   | | |/ __| |/ / | | |" Blue
    Say "  | |  | | (_) | (_) | (_| | |  __/ |___| | | (__|   <| |_| |" Blue
    Say "  |_|  |_|\___/ \___/ \__,_|_|\___|\____|_|_|\___|_|\_\\__, |" Blue
    Say "                                                       |___/ " Blue
    Say "   your cursor study buddy" DarkGray
    Say ""
}

function Ask($question, $default = "") {
    $hint = if ($default) { " [$default]" } else { "" }
    $a = Read-Host "  $question$hint"
    if ([string]::IsNullOrWhiteSpace($a)) { return $default } else { return $a.Trim() }
}

function AskYesNo($question, [bool]$default = $true) {
    $d = if ($default) { "Y/n" } else { "y/N" }
    while ($true) {
        $a = Read-Host "  $question ($d)"
        if ([string]::IsNullOrWhiteSpace($a)) { return $default }
        if ($a -match '^(y|yes)$') { return $true }
        if ($a -match '^(n|no)$') { return $false }
    }
}

function AskChoice($question, $options, $defaultIndex) {
    Say "  $question" White
    for ($i = 0; $i -lt $options.Count; $i++) {
        $mark = if ($i -eq $defaultIndex) { "*" } else { " " }
        Say ("   {0} [{1}] {2}" -f $mark, ($i + 1), $options[$i])
    }
    while ($true) {
        $a = Read-Host "  Choose 1-$($options.Count) [$($defaultIndex + 1)]"
        if ([string]::IsNullOrWhiteSpace($a)) { return $defaultIndex }
        $n = 0
        if ([int]::TryParse($a, [ref]$n) -and $n -ge 1 -and $n -le $options.Count) { return $n - 1 }
    }
}

function AskSecret($question) {
    if ([Console]::IsInputRedirected) { return (Read-Host "  $question").Trim() }  # piped/scripted input
    $sec = Read-Host "  $question" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Stop-App {
    $procs = Get-Process -Name "MoodleClicky" -ErrorAction SilentlyContinue
    if ($procs) {
        Say "  Closing the running MoodleClicky..."
        $procs | Stop-Process -Force
        Start-Sleep -Seconds 1
    }
}

function New-Shortcut($path, $target, $arguments = "", $icon = $Exe) {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($path)
    $sc.TargetPath = $target
    $sc.Arguments = $arguments
    $sc.WorkingDirectory = $Dir
    $sc.IconLocation = $icon
    $sc.Save()
}

function Install-App {
    Step "Getting the latest MoodleClicky"
    $tmp = Join-Path $env:TEMP ("moodleclicky-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        if ($Zip) {
            $zipPath = (Resolve-Path $Zip).Path
            Say "  Using $zipPath"
        } else {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            try {
                $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ "User-Agent" = "MoodleClicky-installer" }
            } catch {
                throw "Couldn't find a MoodleClicky release on GitHub (is the repo private, or offline?). Download MoodleClicky-windows.zip yourself and run:  .\install.ps1 -Zip <path-to-zip>"
            }
            $asset = $rel.assets | Where-Object { $_.name -eq "MoodleClicky-windows.zip" } | Select-Object -First 1
            if (-not $asset) { throw "Release $($rel.tag_name) has no MoodleClicky-windows.zip" }
            $zipPath = Join-Path $tmp "MoodleClicky-windows.zip"
            Say ("  Downloading {0} ({1:N0} MB)..." -f $rel.tag_name, ($asset.size / 1MB))
            Invoke-WebRequest $asset.browser_download_url -OutFile $zipPath -UseBasicParsing -Headers @{ "User-Agent" = "MoodleClicky-installer" }
        }

        Say "  Unpacking..."
        Expand-Archive -Path $zipPath -DestinationPath (Join-Path $tmp "x") -Force
        $src = Get-ChildItem (Join-Path $tmp "x") -Recurse -Filter "MoodleClicky.exe" | Select-Object -First 1
        if (-not $src) { throw "MoodleClicky.exe not found in the zip" }

        Stop-App
        if (Test-Path $Dir) {
            Say "  Removing the old version..."
            Remove-Item $Dir -Recurse -Force
        }
        New-Item -ItemType Directory -Path (Split-Path $Dir) -Force | Out-Null
        Move-Item $src.DirectoryName $Dir
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # Keep a copy of this script for the Setup / Uninstall shortcuts.
    $self = Join-Path $Dir "install.ps1"
    if ($PSCommandPath -and (Test-Path $PSCommandPath)) { Copy-Item $PSCommandPath $self -Force }
    else { try { Invoke-WebRequest $RawScript -OutFile $self -UseBasicParsing } catch { Say "  (couldn't save install.ps1 locally - Setup shortcut skipped)" Yellow } }

    Step "Adding shortcuts"
    New-Shortcut (Join-Path $StartMenu "MoodleClicky.lnk") $Exe
    New-Shortcut (Join-Path $Desktop "MoodleClicky.lnk") $Exe
    if (Test-Path $self) {
        $ps = (Get-Command powershell.exe).Source
        New-Shortcut (Join-Path $StartMenu "MoodleClicky Setup.lnk") $ps "-NoProfile -ExecutionPolicy Bypass -File `"$self`" -Setup"
        New-Shortcut (Join-Path $StartMenu "Uninstall MoodleClicky.lnk") $ps "-NoProfile -ExecutionPolicy Bypass -File `"$self`" -Uninstall"
    }
    Say "  Start menu + Desktop: MoodleClicky" Green
}

function Read-CurrentSettings {
    $cfg = Join-Path $Data "config.json"
    if (Test-Path $cfg) { try { return Get-Content $cfg -Raw | ConvertFrom-Json } catch { } }
    return $null
}

function Show-SetupMenu {
    Banner
    Say "  Setup - press Enter to keep the value in [brackets]." White
    Say ""
    $cur = Read-CurrentSettings
    $provIdx = if ($cur -and $cur.provider -eq "deepseek") { 1 } else { 0 }
    $p = AskChoice "Which AI should explain things?" @("Claude (Anthropic) - best explanations", "DeepSeek - much cheaper") $provIdx
    $provider = @("anthropic", "deepseek")[$p]
    $where = if ($provider -eq "anthropic") { "console.anthropic.com -> API keys (starts with sk-ant-)" } else { "platform.deepseek.com -> API keys" }
    Say ""
    Say "  Get a key at: $where" DarkGray
    $key = AskSecret "Paste your API key (hidden; Enter = keep the saved one)"
    Say ""
    $name = Ask "Your first name (so group-meeting notes can find YOUR tasks)" $(if ($cur) { $cur.your_name } else { "" })
    $course = Ask "Your course (optional, e.g. Birkbeck BSc Computer Science Y2)" $(if ($cur) { $cur.course_context } else { "" })
    Say ""
    $auto = AskYesNo "Start MoodleClicky when Windows starts?" $(if ($cur) { [bool]$cur.start_with_windows } else { $true })
    Say ""
    Say "  Lecture / meeting notetaker" White
    $mic = AskYesNo "Record your microphone (in-person lectures, group meetings)?" $(if ($cur) { [bool]$cur.record_mic } else { $true })
    $sys = AskYesNo "Record computer audio (Teams / Zoom / Panopto)?" $(if ($cur) { [bool]$cur.record_system } else { $true })
    $models = @("tiny.en", "base.en", "small.en", "medium.en")
    $mIdx = if ($cur -and ($models -contains $cur.whisper_model)) { [array]::IndexOf($models, $cur.whisper_model) } else { 2 }
    $m = AskChoice "Speech-to-text quality (downloads on first use)" @("tiny  - fastest, rough", "base  - fast", "small - good balance (~250 MB)", "medium - best, slow on older laptops") $mIdx

    $payload = [ordered]@{
        provider = $provider; your_name = $name; course_context = $course; start_with_windows = $auto
        record_mic = $mic; record_system = $sys; whisper_model = $models[$m]; buddy_visible = $true
    }
    if ($key) { $payload.api_key = $key }

    Step "Saving"
    $env:MOODLECLICKY_SETUP = ($payload | ConvertTo-Json -Compress)
    try {
        $proc = Start-Process -FilePath $Exe -ArgumentList "--apply-setup" -Wait -PassThru
    } finally {
        Remove-Item Env:\MOODLECLICKY_SETUP -ErrorAction SilentlyContinue
        $payload = $null
    }
    $log = Join-Path $Data "setup.log"
    if (Test-Path $log) { Get-Content $log | ForEach-Object { Say "    $_" DarkGray } }
    if ($proc.ExitCode -ne 0) { throw "Saving settings failed (see above)." }
    if (-not $key -and -not $cur) { Say "  No API key yet - the app will ask for one when it opens." Yellow }
    Say "  Saved." Green
}

function Start-AppNow {
    Step "Starting MoodleClicky"
    Start-Process -FilePath $Exe
    Say ""
    Say "  It lives in your system tray (bottom-right, by the clock)." White
    Say ""
    Say "    Ctrl + Alt + Space   ask about what's under your mouse"
    Say "    Ctrl + Alt + N       lecture / meeting notetaker"
    Say "    Ctrl + Alt + M       mark an important moment while recording"
    Say "    Ctrl + Alt + H       show / hide the buddy"
    Say ""
    Say "  Change anything later: tray icon -> Settings, or Start menu -> MoodleClicky Setup." DarkGray
    Say ""
}

function Uninstall-App {
    Banner
    Say "  Uninstall MoodleClicky" White
    Stop-App
    try {
        Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MoodleClicky" -ErrorAction SilentlyContinue
    } catch { }
    foreach ($lnk in @((Join-Path $StartMenu "MoodleClicky.lnk"), (Join-Path $StartMenu "MoodleClicky Setup.lnk"),
                       (Join-Path $StartMenu "Uninstall MoodleClicky.lnk"), (Join-Path $Desktop "MoodleClicky.lnk"))) {
        Remove-Item $lnk -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $Dir) {
        # This script may be running from inside $Dir - delete via a short-lived helper.
        Start-Process -WindowStyle Hidden cmd.exe -ArgumentList "/c timeout /t 2 >nul & rmdir /s /q `"$Dir`""
    }
    Say "  App removed." Green
    if (AskYesNo "Also delete your settings, saved API keys, notes and lecture transcripts?" $false) {
        Remove-Item $Data -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($t in @("MoodleClicky", "anthropic_api_key@MoodleClicky", "deepseek_api_key@MoodleClicky")) {
            cmdkey /delete:$t 2>$null | Out-Null
        }
        Say "  Settings, keys and notes deleted." Green
    } else {
        Say "  Kept your notes in $Data" DarkGray
    }
}

try {
    if ($Uninstall) {
        Uninstall-App
    } elseif ($Setup) {
        if (-not (Test-Path $Exe)) { throw "MoodleClicky isn't installed yet - run the install command first." }
        Show-SetupMenu
        Stop-App
        Start-AppNow
    } else {
        Banner
        Say "  Installing to $Dir" DarkGray
        Install-App
        Show-SetupMenu
        Start-AppNow
        Say "  All done!" Green
    }
} catch {
    Say ""
    Say "  Something went wrong: $($_.Exception.Message)" Red
    Say "  Nothing else was changed. You can run the command again." DarkGray
}
if ($Setup -or $Uninstall) { Read-Host "  Press Enter to close" | Out-Null }
