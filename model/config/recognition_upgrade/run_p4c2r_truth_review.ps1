param(
    [ValidateSet('Prepare', 'Review', 'Check')]
    [string]$Command = 'Check'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Project Python not found: $Python" }
$Subcommand = $Command.ToLowerInvariant()
Push-Location -LiteralPath $ProjectRoot
try {
    & $Python -m eval.runtime_diagnostics.p4c2r_truth_review $Subcommand
    if ($LASTEXITCODE -ne 0) { throw "P4-C2R $Command failed." }
}
finally {
    Pop-Location
}
