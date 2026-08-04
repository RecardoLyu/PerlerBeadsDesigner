allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

// 注：插件 compileSdk 不一致问题（file_picker=34 vs flutter_plugin_android_lifecycle
// 要求>=36）此前靠手动改 pub-cache 插件源码绕过，CI 干净环境拉原版即失败（不可移植）。
// 改为在配置阶段统一覆写所有 Android 库插件的 compileSdk（见下），对 CI/本地都生效。

// 在所有 project 配置完成后，把每个 Android 库插件的 compileSdk 对齐到 36。
// 用安全包装：project 已 evaluate 则直接执行，否则注册 afterEvaluate 回调。
// （evaluationDependsOn(":app") 使部分插件 project 先 evaluate，裸 afterEvaluate 会抛
// "Cannot run afterEvaluate when already evaluated"，故需 state.executed 判断。）
val REQUIRED_COMPILE_SDK = 36
fun Project.alignCompileSdk() {
    plugins.withId("com.android.library") {
        val androidExt = extensions.findByName("android")
        if (androidExt is com.android.build.gradle.LibraryExtension) {
            val cur = androidExt.compileSdkVersion?.removePrefix("android-")?.toIntOrNull() ?: 0
            if (cur < REQUIRED_COMPILE_SDK) {
                androidExt.compileSdk = REQUIRED_COMPILE_SDK
            }
        }
    }
}
rootProject.allprojects {
    if (state.executed) alignCompileSdk() else afterEvaluate { alignCompileSdk() }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
