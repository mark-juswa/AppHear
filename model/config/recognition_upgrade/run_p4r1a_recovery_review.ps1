param(
    [ValidateSet("Review", "Status")]
    [string]$Command = "Review"
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "P4-R1A project Python was not found: $python"
}

Push-Location $projectRoot
try {
    if ($Command -eq "Status") {
        & $python -m eval.runtime_diagnostics.p4r1a_recovery_review --status
    } else {
        & $python -m eval.runtime_diagnostics.p4r1a_recovery_review
    }
    if ($LASTEXITCODE -ne 0) { throw "P4-R1A $Command failed." }
}
finally {
    Pop-Location
}
