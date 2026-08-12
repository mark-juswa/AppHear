$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$dockerfile = Join-Path $PSScriptRoot "c0b_model_maker.Dockerfile"
$imageName = "apphear-c0b-model-maker:0.2.1.4"
$runDir = "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01"
$manifestRun = "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01"

Set-Location $projectRoot

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start Docker Desktop and rerun this script."
}

docker build --file $dockerfile --tag $imageName $PSScriptRoot
if ($LASTEXITCODE -ne 0) {
    throw "C0-B0 Docker image build failed. Preserve the complete log and stop."
}

$candidates = @(
    @("mobilenet_v2_100", "$runDir/models/mobilenet_v2_100/export/model_float.tflite"),
    @("mobilenet_v2_i320_100", "$runDir/models/mobilenet_v2_i320_100/export/model_float.tflite")
)

foreach ($candidate in $candidates) {
    $name = $candidate[0]
    $model = $candidate[1]
    Write-Host "Evaluating research-only development candidate: $name"
    docker run --rm `
        --mount "type=bind,source=$projectRoot,target=/workspace" `
        $imageName `
        python -m pipeline.tracking.e2e_c0b_stage2_eval run-model `
        --run-dir $runDir `
        --manifest-run $manifestRun `
        --candidate $name `
        --model $model `
        --retry-incomplete
    if ($LASTEXITCODE -ne 0) {
        throw "C0-B0 development evaluation failed for $name. Preserve output and stop."
    }
}

docker run --rm `
    --mount "type=bind,source=$projectRoot,target=/workspace" `
    $imageName `
    python -m pipeline.tracking.e2e_c0b_stage2_eval compare `
    --run-dir $runDir `
    --candidates mobilenet_v2_100 mobilenet_v2_i320_100
if ($LASTEXITCODE -ne 0) {
    throw "C0-B0 development comparison failed. Preserve output and stop."
}

Write-Host "C0-B0 development threshold comparison completed: $runDir/development_evaluation"
