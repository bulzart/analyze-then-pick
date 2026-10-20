# Windows wrapper: finds Python 3.10+ and runs install.py with the same arguments.
# Usage:  powershell -ExecutionPolicy Bypass -File install.ps1 [--force] [--no-deps] [--no-mcp] [--dry-run]
$ErrorActionPreference = 'Stop'
$py = $null
foreach ($c in @('py', 'python', 'python3')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source; break }
}
if (-not $py) { Write-Host 'Python 3.10+ not found. Install it (winget install Python.Python.3.12), then run this again.'; exit 1 }
$exe = & $py -c "import sys; print(sys.executable)"
& $exe (Join-Path $PSScriptRoot 'install.py') @args
exit $LASTEXITCODE
