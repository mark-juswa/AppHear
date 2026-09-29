param(
    [string]$Output = 'G:\3d Characters\optimized_apphear3_batch',
    [string[]]$Signs = @(),
    [switch]$PlanOnly
)
$ErrorActionPreference = 'Stop'
$taskRepo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$taskRuntime = Join-Path $taskRepo 'artifacts\text_to_asl_asset_optimization_20260928\tools'
if (-not (Test-Path -LiteralPath (Join-Path $taskRuntime 'node_modules'))) {
    throw 'Pinned pilot dependencies are missing. See tools/text_to_asl_assets/README.md.'
}
$taskArguments = @((Join-Path $PSScriptRoot 'batch.mjs'), '--runtime', $taskRuntime, '--output', $Output)
if ($Signs.Count -gt 0) { $taskArguments += @('--signs', ($Signs -join ',')) }
if ($PlanOnly) { $taskArguments += '--plan' }
& node @taskArguments
if ($LASTEXITCODE -ne 0) { throw "Asset batch failed (exit $LASTEXITCODE). See its reports folder." }
