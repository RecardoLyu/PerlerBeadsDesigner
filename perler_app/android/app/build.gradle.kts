plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// release 签名：优先读 android/key.properties（本地，gitignore 排除）；
// CI 在构建前由 Secrets 生成同样的 key.properties。两者用同一 keystore → 签名一致，
// 在线更新可覆盖安装。无 key.properties（他人 clone 源码）时回退 debug 签名，仍可正常开发。
import java.util.Properties
val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
val hasReleaseKey = keystorePropertiesFile.exists()
if (hasReleaseKey) {
    keystoreProperties.load(keystorePropertiesFile.inputStream())
}

android {
    namespace = "com.recardo.perler.perler_app"
    // file_picker 等插件要求 compileSdk >= 36（release 构建的 AAR 元数据校验）；
    // 这里显式提到 36。targetSdk 保持 flutter 默认，避免引入新运行时行为。
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.recardo.perler.perler_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // 注：opencv_dart 的 OpenCV 离线缓存通过系统环境变量 DARTCV_CACHE_DIR 提供
        // （Gradle 的 cmake arguments 不支持按 ABI 传不同 OpenCV_DIR，故不用 arguments）。
    }

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            // 有正式 keystore 用 release 签名（与 CI 一致，可覆盖安装）；
            // 否则回退 debug 签名，保证 `flutter run --release` 在他人机器上也能跑。
            signingConfig = if (hasReleaseKey)
                signingConfigs.getByName("release")
            else
                signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
