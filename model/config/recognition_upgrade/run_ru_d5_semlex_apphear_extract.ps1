$ErrorActionPreference = 'Stop'

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
Set-Location -LiteralPath $ProjectRoot

Write-Host 'RU-D5 SEM-LEX CANONICAL APPHEAR EXTRACTION'
Write-Host 'Processes only the 34 clips that passed bounded visual review.'
Write-Host 'Uses frozen offline training D1/D2, not Android runtime S5.'
Write-Host 'Invalid D1/D2 spans may receive a provisional isolated-clip fallback.'
Write-Host 'ACCEPTABLE_VARIANT rows remain provisional and cannot enter Candidate C automatically.'
Write-Host 'Does not read either Sem-Lex archive, build Candidate C, or train.'

python -m pipeline.splits.ru_d5_semlex_apphear_extract prepare
if ($LASTEXITCODE -ne 0) { throw "RU-D5 extraction preparation failed with exit code $LASTEXITCODE" }

python -m pipeline.splits.ru_d5_semlex_apphear_extract check
if ($LASTEXITCODE -ne 0) { throw "RU-D5 pre-extraction check failed with exit code $LASTEXITCODE" }

python -m pipeline.splits.ru_d5_semlex_apphear_extract extract --workers 2
if ($LASTEXITCODE -ne 0) { throw "RU-D5 AppHear extraction failed with exit code $LASTEXITCODE" }

python -m pipeline.splits.ru_d5_semlex_apphear_extract check --require-complete
if ($LASTEXITCODE -ne 0) { throw "RU-D5 post-extraction check failed with exit code $LASTEXITCODE" }

Write-Host 'RU-D5 APPHEAR EXTRACTION COMPLETE'
Write-Host 'Paste the final console output back into Codex.'
Write-Host 'Main report: artifacts\recognition_upgrade\ru_d5\semlex_candidate_01\apphear_extraction\extraction_summary.json'
