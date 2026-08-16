$ErrorActionPreference = 'Stop'
$scriptPath = $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path (Split-Path $scriptPath -Parent) '..\..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Required project interpreter not found: $python"
}
Set-Location -LiteralPath $repoRoot
$env:TF_ENABLE_ONEDNN_OPTS = '0'

Write-Host 'RU-D6 CONTROLLED A/B/C RETRAINING'
Write-Host 'A = frozen baseline; B = RU-D3 cleanup; C = B + 32 frozen exact-target Sem-Lex rows.'
Write-Host 'Runs production-family TCN seeds 101/202/303 on the shared validation split only.'
Write-Host 'The protected test set is not accessed. Existing completed runs are resumed/skipped.'

& $python -m model.experiments.ru_d6_controlled_abc check --run-dir '.\artifacts\recognition_upgrade\ru_d6\controlled_abc_01' --require-smoke
if ($LASTEXITCODE -ne 0) { throw "RU-D6 preflight failed with exit code $LASTEXITCODE" }

& $python -m model.experiments.ru_d6_controlled_abc train --run-dir '.\artifacts\recognition_upgrade\ru_d6\controlled_abc_01' --resume
if ($LASTEXITCODE -ne 0) { throw "RU-D6 training failed with exit code $LASTEXITCODE" }

& $python -m model.experiments.ru_d6_controlled_abc evaluate --run-dir '.\artifacts\recognition_upgrade\ru_d6\controlled_abc_01'
if ($LASTEXITCODE -ne 0) { throw "RU-D6 evaluation failed with exit code $LASTEXITCODE" }

& $python -m model.experiments.ru_d6_controlled_abc check --run-dir '.\artifacts\recognition_upgrade\ru_d6\controlled_abc_01' --require-smoke --require-models --require-evaluation
if ($LASTEXITCODE -ne 0) { throw "RU-D6 final validation failed with exit code $LASTEXITCODE" }

Write-Host 'RU-D6 COMPLETE'
Write-Host 'Paste the final console output back into Codex.'
Write-Host 'Main report: F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\ru_d6\controlled_abc_01\metrics\abc_validation_report.json'
