plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.example.aslrecorder"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.aslrecorder"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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
    buildFeatures {
        viewBinding = true
    }
    // Keep MediaPipe model files uncompressed so they load quickly from assets
    androidResources {
        noCompress += listOf("tflite", "task")
    }
}

dependencies {
    implementation(libs.appcompat)
    implementation(libs.material)
    implementation(libs.activity)
    implementation(libs.constraintlayout)
    implementation(libs.recyclerview)

    // CameraX
    implementation(libs.camera.core)
    implementation(libs.camera.camera2)
    implementation(libs.camera.lifecycle)
    implementation(libs.camera.view)
    implementation(libs.camera.video)

    // MediaPipe Tasks Vision (HandLandmarker, PoseLandmarker, FaceLandmarker)
    implementation(libs.mediapipe.tasks.vision)

    // Concurrent futures (for CameraX ListenableFuture)
    implementation(libs.concurrent.futures)

    testImplementation(libs.junit)
    androidTestImplementation(libs.ext.junit)
    androidTestImplementation(libs.espresso.core)
}
