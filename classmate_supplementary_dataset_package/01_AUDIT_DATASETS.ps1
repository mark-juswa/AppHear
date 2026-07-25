param(
  [string]$LocalDataset = "F:\ASL DATASET\local"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot "apphear3_pipeline\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python scripts\audit_local_dataset.py --source $LocalDataset --vocab config\deployed_vocab.json --labels config\labels.json --experimental-includes config\include_experimental_labels.json --out reports
Write-Host "Audit complete: reports\audit_report.md"

