param(
    [ValidateSet('Prepare', 'Review', 'Validate')]
    [string]$Command = 'Review'
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }
Push-Location $ProjectRoot
try {
    & $Python -m eval.runtime_diagnostics.p4a2_annotation_tool_v2 $Command.ToLowerInvariant()
    if ($LASTEXITCODE -ne 0) { throw "P4-A2 annotation v2 command failed: $Command" }
}
finally { Pop-Location }
