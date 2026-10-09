$ErrorActionPreference = "Stop"

$scriptPath = $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path (Split-Path $scriptPath -Parent) "..\..\..")).Path
$runDir = Join-Path $repoRoot "artifacts\recognition_upgrade\ru_d4\cleanup_only_ab_01"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Required project interpreter not found: $python"
}

Set-Location -LiteralPath $repoRoot
$env:TF_ENABLE_ONEDNN_OPTS = "0"

Write-Host "RU-D4 cleanup-only controlled retraining" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"
Write-Host "Run directory: $runDir"
Write-Host "Interpreter: $python"
Write-Host "Six runs: 2 datasets x seeds 101, 202, 303; production-family TCN only."
Write-Host "The command is resumable and never accesses the protected test set."

& $python -m model.experiments.ru_d4_cleanup_only_ab check --run-dir $runDir --require-smoke
if ($LASTEXITCODE -ne 0) { throw "RU-D4 preflight check failed" }

& $python -m model.experiments.ru_d4_cleanup_only_ab train --run-dir $runDir --resume
if ($LASTEXITCODE -ne 0) { throw "RU-D4 training failed" }

& $python -m model.experiments.ru_d4_cleanup_only_ab evaluate --run-dir $runDir
if ($LASTEXITCODE -ne 0) { throw "RU-D4 evaluation failed" }

& $python -m model.experiments.ru_d4_cleanup_only_ab check --run-dir $runDir `
    --require-smoke --require-models --require-evaluation
if ($LASTEXITCODE -ne 0) { throw "RU-D4 final check failed" }

Write-Host "RU-D4 COMPLETE" -ForegroundColor Green
Write-Host "Paste the final console output back into Codex."
Write-Host "Main report: $runDir\metrics\ab_validation_report.json"
