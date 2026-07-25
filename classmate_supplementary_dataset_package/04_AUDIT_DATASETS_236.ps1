param(
  [string]$LocalDataset = "F:\ASL DATASET\local"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot "apphear3_pipeline\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python scripts\audit_local_dataset.py --source $LocalDataset --vocab config\deployed_vocab.json --labels config\labels.json --experimental-includes config\include_no_experimental_labels.json --out reports\audit_236
Write-Host "236-class audit complete: reports\audit_236\audit_report.md"
