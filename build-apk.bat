@echo off
REM ============================================================
REM  拼豆图纸生成器 · 安卓一键打包脚本
REM
REM  关键：本脚本会先清掉 Claude Code / sandbox 注入的污染环境。
REM  这些沙盒变量会破坏 JVM 的 AF_UNIX loopback（Selector.open），
REM  导致 gradle daemon 起不来、"Unable to establish loopback connection"。
REM  用 setlocal 隔离 + 显式重设最小环境即可彻底绕开。
REM ============================================================

REM ---- 清掉会污染 JVM 的 sandbox/代理变量（局部，不影响系统）----
setlocal
for %%V in (ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY BAGGAGE ^
            HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY http_proxy https_proxy all_proxy no_proxy) do (
  set "%%V="
)

REM ---- 必要环境变量（全部固定在 D 盘，不回落 C 盘）----
if not exist "D:\SDK\jdk-17.0.19+10\bin\java.exe" (
  echo [build] 错误：缺少 D:\SDK\jdk-17.0.19+10，请先安装 Temurin JDK 17。
  endlocal & exit /b 1
)
set "JAVA_HOME=D:\SDK\jdk-17.0.19+10"
set "ANDROID_HOME=D:\SDK\android-sdk"
set "ANDROID_SDK_ROOT=D:\SDK\android-sdk"
set "GRADLE_USER_HOME=D:\SDK\gradle"
set "ANDROID_USER_HOME=D:\SDK\android-home"
set "PUB_CACHE=D:\pub-cache"
set "DARTCV_CACHE_DIR=D:\WS\PYTHON\PerlerBeadsDesigner\build_cv\dartcv-cache"
set "TEMP=D:\Temp\PerlerBuild"
set "TMP=D:\Temp\PerlerBuild"
set "FLUTTER_SUPPRESS_ANALYTICS=true"
if not exist "D:\Temp\PerlerBuild" mkdir "D:\Temp\PerlerBuild"
if not exist "D:\SDK\android-home" mkdir "D:\SDK\android-home"

REM ---- 只对本构建进程追加 PATH（setlocal 隔离，不污染系统）----
set "PATH=D:\SDK\flutter\bin;%JAVA_HOME%\bin;D:\SDK\android-sdk\platform-tools;D:\SDK\android-sdk\cmdline-tools\latest\bin;%PATH%"

cd /d "%~dp0perler_app\android"

echo [build] JAVA_HOME=%JAVA_HOME%
echo [build] ANDROID_HOME=%ANDROID_HOME%
echo [build] GRADLE_USER_HOME=%GRADLE_USER_HOME%
echo [build] PUB_CACHE=%PUB_CACHE%
echo [build] DARTCV_CACHE_DIR=%DARTCV_CACHE_DIR%
echo.

REM ---- 打包类型：默认 release，可传 debug ----
set "VARIANT=%~1"
if "%VARIANT%"=="" set "VARIANT=release"

if /i "%VARIANT%"=="debug" (
  echo [build] 开始构建 DEBUG APK ...
  call gradlew.bat --no-daemon assembleDebug
) else (
  echo [build] 开始构建 RELEASE APK ...
  call gradlew.bat --no-daemon assembleRelease
)

if errorlevel 1 (
  echo.
  echo [build] ===== 构建失败 =====
  endlocal & exit /b 1
)

echo.
echo [build] ===== 构建成功，APK 位置：=====
dir /b /s "%~dp0perler_app\build\app\outputs\flutter-apk\*.apk" 2>nul
endlocal
