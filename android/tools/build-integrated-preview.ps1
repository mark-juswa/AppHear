param(
    [ValidateSet('fake','private')][string]$Configuration = 'fake',
    [string[]]$Tasks = @('testDebugUnitTest','assembleDebug','assembleDebugAndroidTest')
)
$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$packageDirectory = Join-Path $projectDirectory 'packages/fingerspelling_continuous_v2_1_01'
$options = @('--console=plain','--max-workers=2','-Pandroid.useAndroidX=true',
    '--init-script',(Join-Path $PSScriptRoot 'text-to-sign-test-memory.init.gradle'),
    '-Pfingerspell=true','-PfingerspellContinuous=true',"-PfingerspellArtifactDir=$packageDirectory",
    '-PrecognitionRearCamera=true','-PrecognitionCoordination=true','-PcontextPhraseAssist=true',
    "-PcontextPhraseAssistProvider=$(if ($Configuration -eq 'private') {'gemini'} else {'fake'})",
    '-PaslAssetPilot=true','-PaslSharedCharacter=true','-PaslMoreWords=true',
    '-PaslCharacterSelection=true','-PaslNewIdle=true','-PaslAlphabetFallback=true','-PaslOriginalWords=true')
if ($Configuration -eq 'fake') {
    foreach ($credentialName in @('SUPABASE_URL','SUPABASE_ANON_KEY','APPHEAR_SUPABASE_URL',
        'APPHEAR_SUPABASE_ANON_KEY','APPHEAR_ELEVENLABS_MODEL_ID','APPHEAR_ELEVENLABS_VOICE_ID',
        'APPHEAR_ELEVENLABS_API_KEY','APPHEAR_CONTEXT_ASSIST_API_KEY','APPHEAR_GEMINI_API_KEY')) {
        $options += "-P$credentialName="
    }
}
# These are the existing debug preview flags. No recognition model or thresholds change.
# Other primary-branch experimental flags retain their defaults unless explicitly supplied.
Push-Location (Join-Path $projectDirectory 'android')
try {
    & ./gradlew.bat @Tasks @options
    if ($LASTEXITCODE -ne 0) { throw "Integrated preview build failed: $LASTEXITCODE" }
} finally { Pop-Location }
