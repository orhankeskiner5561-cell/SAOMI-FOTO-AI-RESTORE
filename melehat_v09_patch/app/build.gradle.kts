plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.saomi.telsiz"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.saomi.telsiz"
        minSdk = 26
        targetSdk = 35
        versionCode = 9
        versionName = "0.9.0"

        buildConfigField("String", "LIVEKIT_URL", "\"\"")
        buildConfigField("String", "TOKEN_ENDPOINT", "\"https://ecbzcexhpzntgrfpizxc.supabase.co/functions/v1/livekit-token\"")
        buildConfigField("String", "BACKEND_BASE_URL", "\"https://ecbzcexhpzntgrfpizxc.supabase.co\"")
        buildConfigField("String", "SUPABASE_URL", "\"https://ecbzcexhpzntgrfpizxc.supabase.co\"")
        buildConfigField("String", "SUPABASE_PUBLISHABLE_KEY", "\"sb_publishable_bSEN1Escr9WnT5gdhx2K6w_KoxwjoGB\"")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin { jvmToolchain(17) }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.01.00"))
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.media:media:1.7.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("io.livekit:livekit-android:2.29.0")
}
