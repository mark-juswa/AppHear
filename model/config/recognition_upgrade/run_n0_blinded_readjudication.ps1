param(
    [ValidateSet('Prepare', 'Review', 'Check', 'Finalize', 'Status')]
    [string]$Command = 'Status'
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Config = Join-Path $PSScriptRoot 'n0_blinded_readjudication.json'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project Python not found: $Python"
}

$Mode = $Command.ToLowerInvariant()
Push-Location $Root
try {
    & $Python -m pipeline.tracking.n0_blinded_readjudication $Mode --config $Config
    if ($LASTEXITCODE -ne 0) {
        throw "N0 blinded re-adjudication $Command failed."
    }
}
finally {
    Pop-Location
}

