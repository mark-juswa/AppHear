plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    val profileAccounts = providers.gradleProperty("profileAccounts")
        .map { it.equals("true", ignoreCase = true) }.getOrElse(false)
    val aslAssetPilot = providers.gradleProperty("aslAssetPilot")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val aslSharedCharacter = providers.gradleProperty("aslSharedCharacter")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    require(!aslSharedCharacter || aslAssetPilot) { "aslSharedCharacter requires aslAssetPilot=true" }
    val aslMoreWords = providers.gradleProperty("aslMoreWords")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    require(!aslMoreWords || aslSharedCharacter) { "aslMoreWords requires aslSharedCharacter=true" }
    val aslCharacterSelection = providers.gradleProperty("aslCharacterSelection")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    require(!aslCharacterSelection || aslMoreWords) { "aslCharacterSelection requires aslMoreWords=true" }
    val aslNewIdle = providers.gradleProperty("aslNewIdle")
        .map { it.equals("true", ignoreCase = true) }.getOrElse(false)
    require(!aslNewIdle || aslMoreWords) { "aslNewIdle requires aslMoreWords=true" }
    val aslAlphabetFallback = providers.gradleProperty("aslAlphabetFallback")
        .map { it.equals("true", ignoreCase = true) }.getOrElse(false)
    require(!aslAlphabetFallback || (aslNewIdle && aslCharacterSelection)) {
        "aslAlphabetFallback requires aslNewIdle=true and aslCharacterSelection=true"
    }
    if (aslSharedCharacter) {
        val sharedAssets = tasks.register<Sync>("prepareAslSharedAssets") {
            from("src/aslPilot/assets") { exclude("asl_animations/vnext/**") }
            from(when {
                aslAlphabetFallback -> "src/aslAlphabet/assets"
                aslNewIdle -> "src/aslIdle/assets"
                aslMoreWords -> "src/aslWords/assets"
                else -> "src/aslShared/assets"
            })
            into(layout.buildDirectory.dir("generated/aslSharedAssets"))
        }
        sourceSets.getByName("debug").assets.srcDir(layout.buildDirectory.dir("generated/aslSharedAssets"))
        tasks.configureEach { if (name == "mergeDebugAssets") dependsOn(sharedAssets) }
    } else if (aslAssetPilot) {
        sourceSets.getByName("debug").assets.srcDir("src/aslPilot/assets")
    }
    val elevenLabsApiKey = providers.gradleProperty("APPHEAR_ELEVENLABS_API_KEY")
        .orElse(providers.environmentVariable("APPHEAR_ELEVENLABS_API_KEY"))
        .orNull
        .orEmpty()
    val elevenLabsVoiceId = providers.gradleProperty("APPHEAR_ELEVENLABS_VOICE_ID")
        .orElse(providers.environmentVariable("APPHEAR_ELEVENLABS_VOICE_ID"))
        .orNull
        .orEmpty()
    val elevenLabsModelId = providers.gradleProperty("APPHEAR_ELEVENLABS_MODEL_ID")
        .orElse(providers.environmentVariable("APPHEAR_ELEVENLABS_MODEL_ID"))
        .orNull
        .orEmpty()
    val supabaseUrl = providers.gradleProperty("APPHEAR_SUPABASE_URL")
        .orElse(providers.gradleProperty("SUPABASE_URL"))
        .orElse(providers.environmentVariable("APPHEAR_SUPABASE_URL"))
        .orElse(providers.environmentVariable("SUPABASE_URL"))
        .orNull
        .orEmpty()
    val supabaseAnonKey = providers.gradleProperty("APPHEAR_SUPABASE_ANON_KEY")
        .orElse(providers.gradleProperty("SUPABASE_ANON_KEY"))
        .orElse(providers.environmentVariable("APPHEAR_SUPABASE_ANON_KEY"))
        .orElse(providers.environmentVariable("SUPABASE_ANON_KEY"))
        .orNull
        .orEmpty()
    val phase1ShadowDebug = providers.gradleProperty("phase1Shadow")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val ruD1Debug = providers.gradleProperty("ruD1")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val ruD10ObservationContinuity = providers.gradleProperty("ruD10A")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val ruD10S5OneShortGap = providers.gradleProperty("ruD10B")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val a1IndependentClock = providers.gradleProperty("a1IndependentClock")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val perceptionVNextDebug = providers.gradleProperty("perceptionVNext")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val phoneCausalRecognitionDebug = providers.gradleProperty("phoneCausalRecognition")
        .map { it.equals("true", ignoreCase = true) }
        .getOrElse(false)
    val phoneS2DebugPackage = providers.gradleProperty("apphearPhoneS2Package")
        .orNull
        ?.uppercase()
        ?: "S2_R2_CANDIDATE"
    val contextPhraseAssistDebug = providers.gradleProperty("contextPhraseAssist")
        .map { it.equals("true", ignoreCase = true) }.getOrElse(false)
    val contextPhraseAssistProvider = providers.gradleProperty("contextPhraseAssistProvider")
        .orNull?.lowercase() ?: "fake"
    val contextPhraseCaptureDebug = providers.gradleProperty("contextPhraseCapture")
        .map { it.equals("true", ignoreCase = true) }.getOrElse(false)
    require(contextPhraseAssistProvider in setOf("fake", "remote", "gemini"))
    val contextPhraseAssistApiKey = providers.gradleProperty("APPHEAR_CONTEXT_ASSIST_API_KEY")
        .orElse(providers.environmentVariable("APPHEAR_CONTEXT_ASSIST_API_KEY"))
        .orNull.orEmpty()
    val contextPhraseAssistGeminiApiKey = if (contextPhraseAssistDebug &&
        contextPhraseAssistProvider == "gemini") {
        providers.gradleProperty("APPHEAR_GEMINI_API_KEY")
            .orElse(providers.environmentVariable("APPHEAR_GEMINI_API_KEY"))
            .orNull.orEmpty()
    } else ""
    require(phoneS2DebugPackage in setOf("S2_R2_CANDIDATE", "PHASE7_CONTROL")) {
        "apphearPhoneS2Package must be S2_R2_CANDIDATE or PHASE7_CONTROL"
    }

    namespace = "com.example.apphear"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.apphear"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "ELEVENLABS_API_KEY", "\"$elevenLabsApiKey\"")
        buildConfigField("String", "ELEVENLABS_VOICE_ID", "\"$elevenLabsVoiceId\"")
        buildConfigField("String", "ELEVENLABS_MODEL_ID", "\"$elevenLabsModelId\"")
        buildConfigField("String", "SUPABASE_URL", "\"$supabaseUrl\"")
        buildConfigField("String", "SUPABASE_ANON_KEY", "\"$supabaseAnonKey\"")
    }

    buildTypes {
        debug {
            buildConfigField("boolean", "PROFILE_ACCOUNTS_ENABLED", profileAccounts.toString())
            buildConfigField("boolean", "ASL_ASSET_PILOT_ENABLED", aslAssetPilot.toString())
            buildConfigField("boolean", "ASL_SHARED_CHARACTER_ENABLED", aslSharedCharacter.toString())
            buildConfigField("boolean", "ASL_MORE_WORDS_ENABLED", aslMoreWords.toString())
            buildConfigField("boolean", "ASL_CHARACTER_SELECTION_ENABLED", aslCharacterSelection.toString())
            buildConfigField("boolean", "ASL_NEW_IDLE_ENABLED", aslNewIdle.toString())
            buildConfigField("boolean", "ASL_ALPHABET_FALLBACK_ENABLED", aslAlphabetFallback.toString())
            buildConfigField("String", "APP_PHONE_S2_PACKAGE", "\"$phoneS2DebugPackage\"")
            buildConfigField("boolean", "CONTEXT_PHRASE_ASSIST_ENABLED", contextPhraseAssistDebug.toString())
            buildConfigField("boolean", "CONTEXT_PHRASE_CAPTURE_ENABLED", contextPhraseCaptureDebug.toString())
            buildConfigField("String", "CONTEXT_PHRASE_ASSIST_PROVIDER", "\"$contextPhraseAssistProvider\"")
            buildConfigField("String", "CONTEXT_PHRASE_ASSIST_API_KEY", "\"$contextPhraseAssistApiKey\"")
            buildConfigField("String", "CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY",
                "\"$contextPhraseAssistGeminiApiKey\"")
            buildConfigField("boolean", "PHASE1_SHADOW_ENABLED", phase1ShadowDebug.toString())
            buildConfigField("boolean", "RU_D1_ENABLED", ruD1Debug.toString())
            buildConfigField(
                "boolean",
                "RU_D10_OBSERVATION_CONTINUITY_ENABLED",
                ruD10ObservationContinuity.toString(),
            )
            buildConfigField("boolean", "RU_D10_S5_ONE_SHORT_GAP_ENABLED", ruD10S5OneShortGap.toString())
            buildConfigField("boolean", "A1_INDEPENDENT_CLOCK_ENABLED", a1IndependentClock.toString())
            buildConfigField("boolean", "PERCEPTION_VNEXT_ENABLED", perceptionVNextDebug.toString())
            buildConfigField(
                "boolean",
                "PHONE_CAUSAL_RECOGNITION_ENABLED",
                phoneCausalRecognitionDebug.toString(),
            )
        }
        release {
            buildConfigField("boolean", "PROFILE_ACCOUNTS_ENABLED", "false")
            buildConfigField("boolean", "ASL_ASSET_PILOT_ENABLED", "false")
            buildConfigField("boolean", "ASL_SHARED_CHARACTER_ENABLED", "false")
            buildConfigField("boolean", "ASL_MORE_WORDS_ENABLED", "false")
            buildConfigField("boolean", "ASL_CHARACTER_SELECTION_ENABLED", "false")
            buildConfigField("boolean", "ASL_NEW_IDLE_ENABLED", "false")
            buildConfigField("boolean", "ASL_ALPHABET_FALLBACK_ENABLED", "false")
            buildConfigField("String", "APP_PHONE_S2_PACKAGE", "\"S2_R2_CANDIDATE\"")
            buildConfigField("boolean", "CONTEXT_PHRASE_ASSIST_ENABLED", "false")
            buildConfigField("boolean", "CONTEXT_PHRASE_CAPTURE_ENABLED", "false")
            buildConfigField("String", "CONTEXT_PHRASE_ASSIST_PROVIDER", "\"disabled\"")
            buildConfigField("String", "CONTEXT_PHRASE_ASSIST_API_KEY", "\"\"")
            buildConfigField("String", "CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY", "\"\"")
            isMinifyEnabled = false
            buildConfigField("boolean", "PHASE1_SHADOW_ENABLED", "false")
            buildConfigField("boolean", "RU_D1_ENABLED", "false")
            buildConfigField("boolean", "RU_D10_OBSERVATION_CONTINUITY_ENABLED", "false")
            buildConfigField("boolean", "RU_D10_S5_ONE_SHORT_GAP_ENABLED", "false")
            buildConfigField("boolean", "A1_INDEPENDENT_CLOCK_ENABLED", "false")
            buildConfigField("boolean", "PERCEPTION_VNEXT_ENABLED", "false")
            buildConfigField("boolean", "PHONE_CAUSAL_RECOGNITION_ENABLED", "false")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    // MediaPipe .task models + the TFLite model must stay uncompressed so they can be memory-mapped.
    androidResources {
        noCompress += "task"
        noCompress += "tflite"
        noCompress += "onnx"
    }
    buildFeatures {
        buildConfig = true
        viewBinding = true
    }
}

dependencies {

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.constraintlayout)

    // S0 capture (CameraX) + S1/S2 landmarkers (MediaPipe Tasks Vision) + async (coroutines).
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.mediapipe.tasks.vision)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.navigation.fragment.ktx)
    implementation(libs.androidx.navigation.ui.ktx)
    implementation(libs.androidx.viewpager2)
    implementation(libs.androidx.webkit)

    // S6 recognition: the INT8 streaming model (custom .tflite, separate from MediaPipe's landmarkers).
    implementation(libs.tensorflow.lite)

    // Candidate01 uses the already-parity-checked DWPose-t ONNX runner in the real app.
    implementation(libs.onnxruntime.android)

    testImplementation(libs.junit)
    testImplementation(libs.gson)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
