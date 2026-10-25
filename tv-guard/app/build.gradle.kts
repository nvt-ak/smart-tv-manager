plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.smarttvmanager.guard"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.smarttvmanager.guard"
        // java.time is used by the schedule logic, which needs API 26+.
        minSdk = 26
        targetSdk = 34
        versionCode = 3
        versionName = "0.2.1"
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
    testImplementation("junit:junit:4.13.2")
    // The android.jar stub of org.json throws in JVM unit tests; use the real implementation.
    testImplementation("org.json:json:20240303")
}
