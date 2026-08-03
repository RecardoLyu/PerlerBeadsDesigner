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
// 要求>=36）已通过直接修改 pub-cache 里 file_picker 插件的 build.gradle 解决
// （D:\pub-cache\hosted\pub.dev\file_picker-8.3.7\android\build.gradle 的 compileSdk 34→36）。
// 因 evaluationDependsOn(":app") 导致插件在根脚本注册回调前已 evaluate，
// 根脚本侧的 afterEvaluate/withId 回调对插件不生效，故直接改插件源。

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
