param(
    [ValidateSet('fake','private')][string]$Configuration = 'fake',
    [string[]]$Tasks = @('testDebugUnitTest','assembleDebug','assembleDebugAndroidTest')
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$packageDirectory = Join-Path $repositoryRoot 'packages/fingerspelling_continuous_v2_1_01'
$inventory = Get-Content -LiteralPath (Join-Path $packageDirectory 'package_inventory.json') -Raw | ConvertFrom-Json
foreach ($entry in $inventory.files) {
    $assetPath = Join-Path $packageDirectory $entry.path
    if ((Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Frozen package integrity mismatch: $($entry.path)"
    }
}
# Use JDK17 and the existing local Android SDK configuration. Never embed secrets here.
$options = @('--console=plain','--no-daemon','--max-workers=2','-Pandroid.useAndroidX=true',
    '-Pfingerspell=true','-PfingerspellContinuous=true',"-PfingerspellArtifactDir=$packageDirectory",
    '-PrecognitionRearCamera=true','-PrecognitionCoordination=true',
    '-PcontextPhraseAssist=true',"-PcontextPhraseAssistProvider=$(if ($Configuration -eq 'private') {'gemini'} else {'fake'})",
    '-PaslAssetPilot=true','-PaslSharedCharacter=true','-PaslMoreWords=true',
    '-PaslCharacterSelection=true','-PaslNewIdle=true','-PaslAlphabetFallback=true')
if ($Configuration -eq 'fake') {
    # Explicit Gradle properties override both local files and inherited environment.
    foreach ($credentialName in @('SUPABASE_URL','SUPABASE_ANON_KEY','APPHEAR_SUPABASE_URL',
        'APPHEAR_SUPABASE_ANON_KEY','APPHEAR_ELEVENLABS_MODEL_ID','APPHEAR_ELEVENLABS_VOICE_ID',
        'APPHEAR_ELEVENLABS_API_KEY','APPHEAR_CONTEXT_ASSIST_API_KEY','APPHEAR_GEMINI_API_KEY')) {
        $options += "-P$credentialName="
    }
}
# private reads the existing Gradle properties/environment. Its APK must stay private.
Push-Location -LiteralPath (Join-Path $repositoryRoot 'android')
try {
    & .\gradlew.bat @Tasks @options
    if ($LASTEXITCODE -ne 0) { throw "Baseline build failed: $LASTEXITCODE" }
} finally { Pop-Location }
