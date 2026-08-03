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

REM ---- 必要环境变量 ----
set "PUB_CACHE=D:\pub-cache"
set "DARTCV_CACHE_DIR=D:\WS\PYTHON\PerlerBeadsDesigner\build_cv\dartcv-cache"

REM ---- 选 JDK：优先 D:\SDK 的 JDK 17（Gradle 9.1 支持 17-24），退回 AS 自带 jbr ----
if exist "D:\SDK\jdk-17.0.19+10\bin\java.exe" (
  set "JAVA_HOME=D:\SDK\jdk-17.0.19+10"
) else if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
  set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
)

cd /d "%~dp0perler_app\android"

echo [build] JAVA_HOME=%JAVA_HOME%
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
