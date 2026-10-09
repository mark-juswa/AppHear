$ErrorActionPreference = 'Stop'

$projectRoot = 'F:\ASL DATASET\5. Apphear3'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$metadata = 'D:\Downloads\semlex_metadata.csv'
$videoArchive = 'D:\Downloads\train.tar.gz'
$poseArchive = 'D:\Downloads\sem-lex-train-poses.tar.gz'
$output = Join-Path $projectRoot 'artifacts\recognition_upgrade\ru_d5\semlex_candidate_01'

Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python is missing: $python"
}
foreach ($required in @($metadata, $videoArchive, $poseArchive)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Sem-Lex input is missing: $required"
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $output 'semlex_screening_manifest.csv') -PathType Leaf)) {
    throw "Prepared RU-D5 manifest is missing. Do not scan the archives without the reviewed selection manifest."
}

Write-Host 'RU-D5 SEM-LEX SELECTIVE EXTRACTION'
Write-Host "Manifest: $output\semlex_screening_manifest.csv"
Write-Host 'This streams both tar.gz archives once and writes only selected TRAIN video/pose members.'
Write-Host 'It does not unpack either archive, run MediaPipe, accept clips, build Candidate C, or train.'

if (-not (Test-Path -LiteralPath (Join-Path $output 'archive_member_resolution.csv') -PathType Leaf)) {
    & $python -m pipeline.splits.ru_d5_semlex_candidate prepare-recovery `
        --metadata $metadata `
        --video-archive $videoArchive `
        --pose-archive $poseArchive `
        --output $output
    if ($LASTEXITCODE -ne 0) { throw "Recovery preparation failed with exit code $LASTEXITCODE" }
}

$resolution = Import-Csv -LiteralPath (Join-Path $output 'archive_member_resolution.csv')
if ($resolution.archive_video_status -contains 'CANONICAL_MEMBER_MISSING_ALT_PATH_AUDIT_PENDING') {
    throw 'Missing-member audit is pending. Run run_ru_d5_semlex_missing_audit_and_poses.ps1; existing videos will not be rescanned.'
}

& $python -m pipeline.splits.ru_d5_semlex_candidate extract-selected `
    --metadata $metadata `
    --video-archive $videoArchive `
    --pose-archive $poseArchive `
    --output $output
if ($LASTEXITCODE -ne 0) { throw "Selective extraction failed with exit code $LASTEXITCODE" }

& $python -m pipeline.splits.ru_d5_semlex_candidate check `
    --output $output `
    --require-extracted
if ($LASTEXITCODE -ne 0) { throw "Post-extraction validation failed with exit code $LASTEXITCODE" }

Write-Host 'RU-D5 SEM-LEX SELECTIVE EXTRACTION COMPLETE'
Write-Host "Summary: $output\selective_extraction_summary.json"
Write-Host "Manifest: $output\selective_extraction_manifest.csv"
