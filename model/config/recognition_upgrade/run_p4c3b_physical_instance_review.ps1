param(
    [ValidateSet('Review', 'Status')]
    [string]$Command = 'Review'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python not found: $python"
}

Push-Location -LiteralPath $projectRoot
try {
    if ($Command -eq 'Status') {
        & $python -m eval.runtime_diagnostics.p4c3b_physical_instance_review --status
    } else {
        & $python -m eval.runtime_diagnostics.p4c3b_physical_instance_review
    }
    if ($LASTEXITCODE -ne 0) {
        throw "P4-C3B $Command failed."
    }
} finally {
    Pop-Location
}
