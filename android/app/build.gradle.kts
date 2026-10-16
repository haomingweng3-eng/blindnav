plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.blindnav.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.blindnav.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Supply from ~/.gradle/gradle.properties or AMAP_API_KEY in the build environment.
        // Never commit an Android key or its signing certificate to this repository.
        manifestPlaceholders["AMAP_API_KEY"] = providers.gradleProperty("AMAP_API_KEY")
            .orElse(providers.environmentVariable("AMAP_API_KEY"))
            .getOrElse("")
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.camera:camera-camera2:1.4.1")
    implementation("androidx.camera:camera-lifecycle:1.4.1")
    implementation("androidx.camera:camera-view:1.4.1")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
    // Combined SDK supplies navigation, map, location and POI search without duplicate AMap jars.
    implementation("com.amap.api:navi-3dmap-location-search:latest.integration")

    testImplementation("junit:junit:4.13.2")
    // Android provides org.json at runtime; this implementation makes the
    // same parser executable in local JVM unit tests instead of framework stubs.
    testImplementation("org.json:json:20240303")
}
