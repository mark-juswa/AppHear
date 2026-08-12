$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$dockerfile = Join-Path $PSScriptRoot "c0b_model_maker.Dockerfile"
$imageName = "apphear-c0b-model-maker:0.2.1.4"
$outputRun = "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01"

Set-Location $projectRoot

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start Docker Desktop and rerun this script."
}

docker build --file $dockerfile --tag $imageName $PSScriptRoot
if ($LASTEXITCODE -ne 0) {
    throw "C0-B0 Docker image build failed. Preserve the complete log and stop."
}

foreach ($fraction in 25, 50, 100) {
    Write-Host "Running research-only MobileNetV2 I320 branch: $fraction%"
    docker run --rm `
        --mount "type=bind,source=$projectRoot,target=/workspace" `
        $imageName `
        python -m pipeline.tracking.e2e_c0b_stage2_train train-one `
        --run-dir $outputRun `
        --model MOBILENET_V2_I320 `
        --fraction $fraction `
        --epochs 30 `
        --batch-size 4 `
        --retry-incomplete
    if ($LASTEXITCODE -ne 0) {
        throw "C0-B0 I320 $fraction% branch failed. Preserve its output and stop."
    }
}

docker run --rm `
    --mount "type=bind,source=$projectRoot,target=/workspace" `
    $imageName `
    python -m pipeline.tracking.e2e_c0b_stage2_train check `
    --run-dir $outputRun `
    --require-models `
    --require-i320
if ($LASTEXITCODE -ne 0) {
    throw "C0-B0 Stage 2 I320 output check failed. Preserve the output and stop."
}

Write-Host "C0-B0 I320 learning curve completed: $outputRun"
