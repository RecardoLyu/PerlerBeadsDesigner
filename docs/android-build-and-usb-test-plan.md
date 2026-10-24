# Android APK 构建与 USB 真机测试计划（全 D 盘）

## 1. 当前检查结论

项目没有丢失 APK 构建能力，现有配置包括：

- 根目录 `build-apk.bat`：可执行 `assembleDebug`／`assembleRelease`。
- Flutter Android 工程：`perler_app/android/`。
- Gradle Wrapper：9.1.0。
- JDK：17；compileSdk 36；minSdk 24。
- Android Gradle Plugin 9.0.1；Kotlin 2.3.20。
- CI 使用 Flutter stable 3.44.8。
- `perler_app/android/local.properties` 已指向 `D:\SDK\flutter` 和 `D:\SDK\android-sdk`。
- Release 构建可读取本地 `key.properties`；没有正式签名时回退 debug 签名。

当前终端未找到 Flutter、Dart、Java、ADB、Gradle 命令，因此本轮没有安装环境、没有构建 APK，也没有声称移动端测试通过。

另外，现有 `build-apk.bat` 仍有回退到 `C:\Program Files\Android\Android Studio\jbr` 的逻辑。严格执行“全部在 D 盘”前，应移除该回退并显式设置所有缓存目录。

## 2. 目标目录与磁盘预算

所有 SDK、JDK、缓存、临时文件和构建产物放在 D 盘：

| 内容 | 计划路径 |
|---|---|
| Flutter SDK | `D:\SDK\flutter` |
| Android SDK | `D:\SDK\android-sdk` |
| JDK 17 | `D:\SDK\jdk-17.0.19+10`（沿用脚本约定） |
| Gradle 用户目录 | `D:\SDK\gradle-home` |
| Android／ADB 用户数据 | `D:\SDK\android-home` |
| Pub 缓存 | `D:\pub-cache` |
| DartCV 缓存 | `D:\WS\PYTHON\PerlerBeadsDesigner\build_cv\dartcv-cache` |
| 构建临时目录 | `D:\Temp\PerlerBuild` |
| 可选 Android Studio | `D:\AndroidStudio`（命令行构建不强制安装） |
| APK 输出 | `D:\WS\PYTHON\PerlerBeadsDesigner\perler_app\build\app\outputs\flutter-apk` |

建议预留至少 **40 GB** 可用空间，覆盖 SDK、多版本 Gradle、Pub／原生依赖和 debug／release 构建缓存。C 盘不主动安装这些组件；构建 shell 中同时把 `TEMP`、`TMP` 指到 D 盘。

## 3. 环境搭建步骤（待批准后执行）

### 阶段 A：固定版本与脚本约束

1. 以 CI 的 Flutter 3.44.8 stable 为基线，避免本地与 CI 使用不同工具链。
2. 准备 Temurin／OpenJDK 17、Android SDK Platform 36、对应 build-tools、platform-tools。
3. 修改 `build-apk.bat`，删除 C 盘 JDK 回退；缺少 D 盘 JDK 时直接给出明确错误。
4. 在构建脚本中显式设置：

```bat
set "JAVA_HOME=D:\SDK\jdk-17.0.19+10"
set "ANDROID_HOME=D:\SDK\android-sdk"
set "ANDROID_SDK_ROOT=D:\SDK\android-sdk"
set "GRADLE_USER_HOME=D:\SDK\gradle-home"
set "ANDROID_USER_HOME=D:\SDK\android-home"
set "PUB_CACHE=D:\pub-cache"
set "DARTCV_CACHE_DIR=D:\WS\PYTHON\PerlerBeadsDesigner\build_cv\dartcv-cache"
set "TEMP=D:\Temp\PerlerBuild"
set "TMP=D:\Temp\PerlerBuild"
set "FLUTTER_SUPPRESS_ANALYTICS=true"
```

5. 只对当前构建终端设置 PATH，不修改系统全局 PATH：
   `D:\SDK\flutter\bin`、JDK `bin`、Android `platform-tools` 和 `cmdline-tools\latest\bin`。
6. 保持 `local.properties` 使用 D 盘路径，不提交个人签名文件或密码。

### 阶段 B：安装与验收

1. 安装／解压上述组件到 D 盘。
2. 接受 Android SDK 许可证，安装 Platform 36 和必要工具。
3. 执行 `flutter doctor -v`，确保 Flutter、Android toolchain、JDK 均来自 D 盘。
4. 执行 `java -version`、`adb version`、`flutter --version`，核对版本。
5. 检查 `flutter pub get`、Gradle 和 DartCV 下载缓存没有回到 C 盘。
6. 若存在组件找不到、插件 compileSdk 或网络下载问题，先修构建链，不通过改 C 盘路径绕过。

验收命令：

```powershell
cd D:\WS\PYTHON\PerlerBeadsDesigner\perler_app
flutter doctor -v
flutter pub get
flutter analyze
flutter test
```

### 阶段 C：APK 构建

先做 debug 包验证安装与核心流程：

```powershell
cd D:\WS\PYTHON\PerlerBeadsDesigner
.\build-apk.bat debug
```

通过后再做 release 包：

```powershell
.\build-apk.bat
```

预期输出：

```text
perler_app\build\app\outputs\flutter-apk\app-debug.apk
perler_app\build\app\outputs\flutter-apk\app-release.apk
```

构建后记录 APK 大小、SHA-256、Flutter／JDK 版本和 Git commit，保证测试结果可追溯。

## 4. 签名策略

- USB 首轮验证优先使用 debug 包，不接触正式密钥。
- 没有 `key.properties` 时，现有 release 构建会使用 debug 签名；它与正式 Release 签名不同，不能假定可以覆盖安装商店／正式发布包。
- 需要验证在线更新或覆盖安装时，必须使用与既有正式版本相同的 keystore。
- `key.properties`、keystore 和密码不得提交仓库、写入日志或放进回复。
- 如签名冲突需要卸载旧应用，会先说明这会清除应用本地数据，得到确认后再执行。

## 5. USB 真机连接计划

### 5.1 准备

1. 手机开启“开发者选项”。
2. 开启“USB 调试”；仅安装 APK 不需要解锁 Bootloader 或 root。
3. 使用支持数据传输的 USB 线连接，手机 USB 用途选择“文件传输”。
4. 手机保持解锁，接受“允许此电脑调试”的 RSA 指纹提示。
5. 电脑只使用 D 盘 Android platform-tools 中的 ADB。

### 5.2 连接验证

```powershell
D:\SDK\android-sdk\platform-tools\adb.exe devices -l
```

状态判断：

- `device`：可以安装测试。
- `unauthorized`：检查手机授权弹窗，撤销旧授权后重连。
- `offline`：重插数据线，必要时重启 ADB，再检查驱动与 USB 模式。
- 无设备：检查数据线、驱动、手机调试开关；不反复安装无关驱动。

### 5.3 安装与启动

```powershell
D:\SDK\android-sdk\platform-tools\adb.exe install -r "D:\WS\PYTHON\PerlerBeadsDesigner\perler_app\build\app\outputs\flutter-apk\app-debug.apk"
D:\SDK\android-sdk\platform-tools\adb.exe shell monkey -p com.recardo.perler.perler_app 1
```

如果 `install -r` 因签名不一致失败，先停止并确认是换用匹配签名包，还是允许卸载旧版本；不自动清除用户数据。

## 6. 真机功能验收清单

### 照片转换

1. 导入照片，默认预览为“真实”。
2. 预览可手动切换“图纸”。
3. 导出区独立选择“真实／图纸／两种”，默认“图纸”。
4. 单风格导出文件名保持原规则；双风格输出 `_real` 与 `_chart`。
5. 两种 PNG 均进入相册，画面、分辨率、标题和 BOM 统计正确。
6. 导出后当前预览风格不被导出选择改变。
7. 移动端没有独立 BOM CSV 导出入口。

### 图纸画板

1. 新建画板，画布预览默认“真实”。
2. 顶部“真实／图纸”切换正常，绘画和撤销重做完好。
3. 导出选择“真实／图纸／两种”，文件名与后缀正确。
4. 双风格内容不同但网格、色号与 BOM 一致。
5. 空画板不能导出，连续点击不会重复并发导出。

### 稳定性

- Android 7.0（API 24）最低系统兼容性与一台主流新系统设备分别验证。
- 测试 1080P、2K、4K；大图导出时观察内存和卡顿。
- 前后台切换、旋转／分屏（若支持）、断网、相册权限拒绝后恢复。
- 记录崩溃与 ANR；必要时用 `adb logcat` 保存对应时间段日志。

## 7. 后续移动端分割性能测试

当前 APK 不包含神经分割。等完成 PNG／风格功能验收后，再按 `docs/u2netp-model-and-mobile-evaluation.md` 单独做 ORT Mobile spike，避免把“APK 可用”和“手机分割性能达标”混为同一次验收。

## 8. 执行顺序

1. 用户确认本计划与 D 盘目录。
2. 修改构建脚本的 D 盘约束，安装并验收工具链。
3. 运行 `flutter analyze`、`flutter test`。
4. 构建 debug APK，完成 USB 安装和功能清单。
5. 构建 release APK，核对签名、大小与哈希。
6. 修复真机问题后复测，再考虑移动端分割 spike。
