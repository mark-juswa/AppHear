param(
    [ValidateSet('Prepare', 'Review', 'Summarize', 'TopUp', 'Check')]
    [string]$Command = 'Review'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }
$Module = 'eval.runtime_diagnostics.p4a2_fresh_evidence_review'

Push-Location $ProjectRoot
try {
    switch ($Command) {
        'Prepare'   { & $Python -m $Module prepare }
        'Review'    { & $Python -m $Module review }
        'Summarize' { & $Python -m $Module summarize }
        'TopUp'     { & $Python -m $Module topup }
        'Check'     { & $Python -m $Module check }
    }
    if ($LASTEXITCODE -ne 0) { throw "P4-A2 evidence-review command failed: $Command" }
}
finally {
    Pop-Location
}
