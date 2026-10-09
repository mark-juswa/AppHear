param(
    [ValidateSet('Prepare', 'Review', 'Check', 'Status', 'Finalize')]
    [string]$Command = 'Status'
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Config = Join-Path $PSScriptRoot 'negative_gold_external_confirmation.json'

Push-Location $Root
try {
    & $Python -m pipeline.tracking.negative_gold_external_confirmation `
        $Command.ToLowerInvariant() --config $Config
    if ($LASTEXITCODE -ne 0) { throw "External confirmation $Command failed." }
}
finally {
    Pop-Location
}
