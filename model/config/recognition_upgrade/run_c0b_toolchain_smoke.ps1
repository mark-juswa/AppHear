$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$dockerfile = Join-Path $PSScriptRoot "c0b_model_maker.Dockerfile"
$imageName = "apphear-c0b-model-maker:0.2.1.4"
$annotationRun = "artifacts/recognition_upgrade/e2e_c0/c0b_annotation_smoke_03"
$outputRun = "artifacts/recognition_upgrade/e2e_c0/c0b_toolchain_smoke_03"

Set-Location $projectRoot

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start Docker Desktop and rerun this script."
}

docker build `
    --file $dockerfile `
    --tag $imageName `
    $PSScriptRoot
if ($LASTEXITCODE -ne 0) {
    throw "C0-B0 Docker image build failed. Preserve the complete log and stop."
}

docker run --rm `
    --mount "type=bind,source=$projectRoot,target=/workspace" `
    $imageName `
    python -m pipeline.tracking.e2e_c0b toolchain-smoke `
    --annotation-run $annotationRun `
    --output $outputRun
if ($LASTEXITCODE -ne 0) {
    throw "C0-B0 one-epoch export/reload smoke failed. Preserve the complete log and stop."
}

Write-Host "C0-B0 toolchain smoke completed: $outputRun"
