param(
  [string]$LocalDataset = "F:\ASL DATASET\local",
  [string]$PreparedRoot = "work\prepared_local_236\AppHearDataset",
  [ValidateSet("hardlink", "copy")][string]$Mode = "hardlink"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot "apphear3_pipeline\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python scripts\prepare_local_dataset.py --source $LocalDataset --out $PreparedRoot --vocab config\deployed_vocab.json --labels config\labels.json --experimental-includes config\include_no_experimental_labels.json --mode $Mode
Write-Host "Prepared 236-class recorder-style dataset: $PreparedRoot"
