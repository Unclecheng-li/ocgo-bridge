<#
=============================================================================
 OpenCode Go Proxy - installer / self-check
=============================================================================
 Run this once after copying the folder to a new machine:

     powershell -ExecutionPolicy Bypass -File install.ps1

 What it does
   1. Finds a working Python 3 interpreter, writes it to python.txt
   2. Creates config.json from config.example.json if you do not have one yet
   3. Runs a self-test against a local mock upstream (no internet needed)
   4. Optionally registers silent autostart (asks first)

 Safe to re-run. Nothing outside this folder is touched unless you say yes to
 autostart.

 If you get "running scripts is disabled", use the -ExecutionPolicy Bypass
 form shown above.
=============================================================================
#>

[CmdletBinding()]
param(
    [switch]$NoAutostart,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Ok($msg)   { Say "  [ok]   $msg" 'Green' }
function Warn($msg) { Say "  [warn] $msg" 'Yellow' }
function Bad($msg)  { Say "  [fail] $msg" 'Red' }
function Head($msg) { Say ""; Say "== $msg ==" 'Cyan' }

Say ""
Say "  OpenCode Go Proxy - installer" 'White'
Say "  $here" 'DarkGray'

# ---------------------------------------------------------------- python ----
Head 'Looking for Python'

$candidates = New-Object System.Collections.Generic.List[string]

# py launcher: most reliable on Windows, version-agnostic
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) { $candidates.Add($pyLauncher.Source) }

# PATH entries
foreach ($n in @('python', 'python3')) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $candidates.Add($c.Source) }
}

# per-user installs
$localPy = Join-Path $env:LOCALAPPDATA 'Programs\Python'
if (Test-Path $localPy) {
    Get-ChildItem $localPy -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'Python3*' } |
        ForEach-Object {
            $exe = Join-Path $_.FullName 'python.exe'
            if (Test-Path $exe) { $candidates.Add($exe) }
        }
}

# machine-wide installs
Get-ChildItem 'C:\' -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'Python3*' } |
    ForEach-Object {
        $exe = Join-Path $_.FullName 'python.exe'
        if (Test-Path $exe) { $candidates.Add($exe) }
    }

$chosen = $null
foreach ($c in ($candidates | Select-Object -Unique)) {
    try {
        $v = & $c -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^3\.(\d+)\.') {
            $minor = [int]$Matches[1]
            if ($minor -ge 9) {
                $chosen = $c
                Ok "$c  (Python $v)"
                break
            } else {
                Warn "$c  (Python $v - need 3.9+)"
            }
        }
    } catch { }
}

if (-not $chosen) {
    Bad 'No usable Python 3.9+ found.'
    Say ''
    Say '  Install Python 3.9 or newer, then re-run this script:' 'Yellow'
    Say '    https://www.python.org/downloads/windows/' 'Yellow'
    Say '  Tick "Add python.exe to PATH" during setup.' 'Yellow'
    exit 1
}

# proxy.py uses only the standard library, so no pip install is needed.
Set-Content -Path (Join-Path $here 'python.txt') -Value $chosen -Encoding ASCII -NoNewline
Ok "saved to python.txt"

# ------------------------------------------------------------------ config --
Head 'Checking config.json'

$cfgPath = Join-Path $here 'config.json'
$exPath  = Join-Path $here 'config.example.json'

if (Test-Path $cfgPath) {
    Ok 'config.json already exists, left untouched'
} else {
    Copy-Item $exPath $cfgPath -Force
    Warn 'created config.json from the example - you MUST edit it'
    Say ''
    Say '  Open config.json in Notepad and set:' 'Yellow'
    Say '    "key"     -> your OpenCode Go API key (starts with oc_sk_)' 'Yellow'
    Say '    "port"    -> listen port, default 8787' 'Yellow'
    Say '  Optional: "http_proxy" only if your network needs a proxy.' 'Yellow'
}

# read back the real values
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$port = if ($cfg.port) { [int]$cfg.port } else { 8787 }
$key  = if ($cfg.key) { [string]$cfg.key } else { '' }
$upstream = if ($cfg.upstream) { [string]$cfg.upstream } else { 'https://opencode.ai/inference/go/v1' }

if ($key -and $key -notmatch 'REPLACE_WITH_YOUR_KEY') {
    Ok ("key configured (" + $key.Length + ' chars)')
    if ($key -match '^oc_sk_') { Ok 'key prefix looks correct (oc_sk_)' }
    else { Warn 'key does not start with oc_sk_ - double check it' }
} else {
    Warn 'no real API key in config.json yet'
}
Ok "port = $port"
Ok "upstream = $upstream"

# --------------------------------------------------------------- self-test --
Head 'Self-test (local mock upstream, no internet needed)'

$selftest = Join-Path $here 'tools\selftest.py'
if (Test-Path $selftest) {
    & $chosen $selftest
    if ($LASTEXITCODE -eq 0) {
        Ok 'self-test passed'
    } else {
        Bad 'self-test FAILED - see output above'
    }
} else {
    Warn 'tools\selftest.py missing from the package; skipped self-test'
}

# --------------------------------------------------------------- autostart --
Head 'Autostart'

$startup = [Environment]::GetFolderPath('Startup')
$link = Join-Path $startup 'OpenCodeGoProxy.vbs'

if ($NoAutostart -or $Yes) {
    $doIt = -not $NoAutostart
} else {
    Say ''
    Say '  Register silent autostart (proxy starts with Windows)?' 'White'
    $ans = Read-Host '  Type Y then Enter to enable, anything else to skip'
    $doIt = ($ans -eq 'Y' -or $ans -eq 'y')
}

if ($doIt) {
    $tpl = Join-Path $here 'startup-template.vbs'
    if (-not (Test-Path $tpl)) {
        Bad 'startup-template.vbs is missing from the package'
    } else {
        Copy-Item $tpl $link -Force
        # The Startup folder copy must be told where the real proxy lives,
        # because it cannot infer that from its own location.
        Set-Content -Path (Join-Path $startup 'proxy_dir.txt') -Value $here -Encoding UTF8
        Ok "installed -> $link"
        Ok "proxy dir -> $startup\proxy_dir.txt"
        Say '    To remove autostart later, delete that .vbs file.' 'DarkGray'
    }
} else {
    Say '  skipped. Start it manually with start-proxy.vbs.' 'DarkGray'
}

# ------------------------------------------------------------------ finish --
Head 'Done'
Say ""
Say "  Start the proxy : double-click start-proxy.vbs" 'White'
Say "  Stop the proxy  : double-click stop-proxy.vbs" 'White'
Say "  See live log    : double-click start.bat" 'White'
Say "  Log file        : $here\proxy.log" 'DarkGray'
Say ""
Say "  Then point your client at:" 'White'
Say "    Base URL (OpenAI)    http://127.0.0.1:$port/v1" 'Green'
Say "    Base URL (Anthropic) http://127.0.0.1:$port/v1" 'Green'
Say "    API key              the same oc_sk_ key from config.json" 'Green'
Say ""
Say "  Verify it is up:" 'White'
Say "    curl http://127.0.0.1:$port/v1/models" 'Green'
Say ""
