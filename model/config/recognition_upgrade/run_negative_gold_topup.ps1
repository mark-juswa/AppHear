param(
    [ValidateSet('Prepare', 'Review', 'Check', 'Status')]
    [string]$Command = 'Status'
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Config = Join-Path $PSScriptRoot 'negative_gold_topup.json'

Push-Location $Root
try {
    & $Python -m pipeline.tracking.negative_gold_governance $Command.ToLowerInvariant() --config $Config
    if ($LASTEXITCODE -ne 0) { throw "Negative-gold top-up $Command failed." }
}
finally {
    Pop-Location
}
