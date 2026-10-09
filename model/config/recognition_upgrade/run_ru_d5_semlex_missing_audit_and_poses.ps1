$ErrorActionPreference = 'Stop'

$projectRoot = 'F:\ASL DATASET\5. Apphear3'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$metadata = 'D:\Downloads\semlex_metadata.csv'
$videoArchive = 'D:\Downloads\train.tar.gz'
$poseArchive = 'D:\Downloads\sem-lex-train-poses.tar.gz'
$output = Join-Path $projectRoot 'artifacts\recognition_upgrade\ru_d5\semlex_candidate_01'

Set-Location -LiteralPath $projectRoot

foreach ($required in @($python, $metadata, $videoArchive, $poseArchive)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required RU-D5 input is missing: $required"
    }
}

Write-Host 'RU-D5 SEM-LEX MISSING-MEMBER AUDIT + VALID-POSE EXTRACTION'
Write-Host 'The 38 existing videos are preserved and are not re-extracted.'
Write-Host 'Pass 1 scans archive names only for the two missing basenames.'
Write-Host 'Pass 2 scans the pose archive only for rows with a valid video.'

& $python -m pipeline.splits.ru_d5_semlex_candidate audit-missing `
    --metadata $metadata `
    --video-archive $videoArchive `
    --pose-archive $poseArchive `
    --output $output
if ($LASTEXITCODE -ne 0) { throw "Missing-member audit failed: $LASTEXITCODE" }

& $python -m pipeline.splits.ru_d5_semlex_candidate extract-selected `
    --metadata $metadata `
    --video-archive $videoArchive `
    --pose-archive $poseArchive `
    --output $output
if ($LASTEXITCODE -ne 0) { throw "Valid-row pose extraction failed: $LASTEXITCODE" }

& $python -m pipeline.splits.ru_d5_semlex_candidate check `
    --output $output `
    --require-extracted
if ($LASTEXITCODE -ne 0) { throw "Post-recovery validation failed: $LASTEXITCODE" }

Write-Host 'RU-D5 SEM-LEX MISSING AUDIT + POSES COMPLETE'
Write-Host "Missing-member result: $output\missing_member_audit_summary.json"
Write-Host "Extraction result: $output\selective_extraction_summary.json"
