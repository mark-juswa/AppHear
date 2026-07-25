param()
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "apphear3_pipeline")
if (-not (Test-Path ".venv")) {
  py -3.11 -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Environment ready. If TensorFlow GPU is not available, training will run on CPU."
