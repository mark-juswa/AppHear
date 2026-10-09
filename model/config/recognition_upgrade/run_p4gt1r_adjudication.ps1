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
    & $Python -m eval.runtime_diagnostics.p4gt1r_adjudication_review $Subcommand
    if ($LASTEXITCODE -ne 0) { throw "P4-GT1R Adjudication $Command failed." }
}
finally {
    Pop-Location
}
