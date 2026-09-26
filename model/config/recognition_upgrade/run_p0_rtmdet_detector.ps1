param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Prepare', 'Evaluate', 'Check')]
    [string]$Command,

    [string]$Output = 'artifacts\recognition_upgrade\perception_backend_replacement\p0_rtmdet_detector_02'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python not found: $python"
}

Set-Location -LiteralPath $repoRoot
$normalizedCommand = $Command.ToLowerInvariant()
& $python -m pipeline.tracking.p0_rtmdet_detector $normalizedCommand --output $Output
if ($LASTEXITCODE -ne 0) {
    throw "P0 $Command failed."
}
