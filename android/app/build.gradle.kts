plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
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
            buildConfigField("boolean", "PHASE1_SHADOW_ENABLED", phase1ShadowDebug.toString())
            buildConfigField("boolean", "RU_D1_ENABLED", ruD1Debug.toString())
            buildConfigField(
                "boolean",
                "RU_D10_OBSERVATION_CONTINUITY_ENABLED",
                ruD10ObservationContinuity.toString(),
            )
            buildConfigField("boolean", "RU_D10_S5_ONE_SHORT_GAP_ENABLED", ruD10S5OneShortGap.toString())
        }
        release {
            isMinifyEnabled = false
            buildConfigField("boolean", "PHASE1_SHADOW_ENABLED", "false")
            buildConfigField("boolean", "RU_D1_ENABLED", "false")
            buildConfigField("boolean", "RU_D10_OBSERVATION_CONTINUITY_ENABLED", "false")
            buildConfigField("boolean", "RU_D10_S5_ONE_SHORT_GAP_ENABLED", "false")
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

    testImplementation(libs.junit)
    testImplementation(libs.gson)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
