$ErrorActionPreference = 'Stop'

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
Set-Location -LiteralPath $ProjectRoot

Write-Host 'RU-D5 FINAL SEM-LEX COME REPLACEMENT EXTRACTION'
Write-Host 'Streams the local TRAIN video archive once for five selected unused COME clips.'
Write-Host 'Does not read supplied poses, run MediaPipe, build Candidate C, or train.'

python -m pipeline.splits.ru_d5_semlex_replacements prepare
if ($LASTEXITCODE -ne 0) { throw "Replacement preparation failed with exit code $LASTEXITCODE" }

python -m pipeline.splits.ru_d5_semlex_replacements extract
if ($LASTEXITCODE -ne 0) { throw "Replacement extraction failed with exit code $LASTEXITCODE" }

python -m pipeline.splits.ru_d5_semlex_replacements check
if ($LASTEXITCODE -ne 0) { throw "Replacement validation failed with exit code $LASTEXITCODE" }

Write-Host 'RU-D5 FINAL REPLACEMENT VIDEO EXTRACTION COMPLETE'
Write-Host 'Paste the final console output back into Codex.'
Write-Host 'Main report: artifacts\recognition_upgrade\ru_d5\semlex_candidate_01\replacement\extraction_summary.json'
