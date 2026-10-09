param(
    [switch]$ApproveFullArchive
)

$ErrorActionPreference = "Stop"

if (-not $ApproveFullArchive) {
    throw "Full 2.71-GiB PopSign WHO download is deferred. Use -ApproveFullArchive only after explicit approval."
}

$scriptPath = $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path (Split-Path $scriptPath -Parent) "..\..\..")).Path
$ruD5Root = Join-Path $repoRoot "artifacts\recognition_upgrade\ru_d5"
$downloadRoot = Join-Path $ruD5Root "inbound\popsign_v1_0\game\train"
$extractRoot = Join-Path $downloadRoot "who"
$partialPath = Join-Path $downloadRoot "who.tar.partial"
$archivePath = Join-Path $downloadRoot "who.tar"
$url = "https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/who.tar"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Required project interpreter not found: $python"
}

New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
$resolvedRuD5 = [System.IO.Path]::GetFullPath($ruD5Root)
$resolvedDownload = [System.IO.Path]::GetFullPath($downloadRoot)
if (-not $resolvedDownload.StartsWith($resolvedRuD5 + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "Download path escaped the RU-D5 artifact root: $resolvedDownload"
}
$drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($resolvedDownload))
$minimumFreeBytes = 6GB
if ($drive.AvailableFreeSpace -lt $minimumFreeBytes) {
    throw "At least 6 GiB free is required for the WHO archive plus extraction"
}

Set-Location -LiteralPath $repoRoot

Write-Host "RU-D5 targeted acquisition: PopSign v1 game/train WHO only" -ForegroundColor Cyan
Write-Host "Source: $url"
Write-Host "Expected archive size: 2,904,832,000 bytes (about 2.71 GiB)"
Write-Host "Available disk space: $([math]::Round($drive.AvailableFreeSpace / 1GB, 2)) GiB"
Write-Host "Destination: $archivePath"
Write-Host "No PopSign validation/test data and no other gloss will be downloaded."

if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    Write-Host "Downloading/resuming WHO archive..."
    & curl.exe --location --fail --continue-at - --output $partialPath $url
    if ($LASTEXITCODE -ne 0) { throw "PopSign WHO download failed" }
    $observedBytes = (Get-Item -LiteralPath $partialPath).Length
    if ($observedBytes -ne 2904832000) {
        throw "WHO archive size mismatch: $observedBytes (expected 2904832000)"
    }
    Move-Item -LiteralPath $partialPath -Destination $archivePath
} else {
    $observedBytes = (Get-Item -LiteralPath $archivePath).Length
    if ($observedBytes -ne 2904832000) {
        throw "Existing WHO archive size mismatch: $observedBytes"
    }
    Write-Host "Verified existing WHO archive; download skipped."
}

$archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
Write-Host "Archive SHA-256: $archiveHash"

if (-not (Test-Path -LiteralPath $extractRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $extractRoot | Out-Null
    Write-Host "Extracting WHO archive..."
    & tar.exe -xf $archivePath -C $extractRoot
    if ($LASTEXITCODE -ne 0) { throw "PopSign WHO extraction failed" }
} else {
    Write-Host "Extraction directory already exists; extraction skipped."
}

$videos = @(Get-ChildItem -LiteralPath $extractRoot -Recurse -File | Where-Object {
    $_.Extension -in ".mp4", ".mov", ".mkv", ".webm"
})
if ($videos.Count -eq 0) {
    throw "No videos found after extracting the PopSign WHO archive"
}

Write-Host "Extracted video files: $($videos.Count)"
& $python -m pipeline.splits.ru_d5_external_supplement check
if ($LASTEXITCODE -ne 0) { throw "RU-D5 metadata check failed" }

Write-Host "RU-D5 POPSIGN WHO ACQUISITION COMPLETE" -ForegroundColor Green
Write-Host "Do not download PopSign val/test or begin MediaPipe extraction yet."
Write-Host "Return the final console output to Codex."
