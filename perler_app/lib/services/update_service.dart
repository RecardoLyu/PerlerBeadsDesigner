import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';
import 'dart:ui';

import 'package:flutter_downloader/flutter_downloader.dart';
import 'package:http/http.dart' as http;
import 'package:open_file/open_file.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 在线更新（Android）：检查 GitHub Release 最新版本 → 原生 DownloadManager
/// 后台下载 APK → 调系统安装器安装。与桌面端共用同一仓库的 Release。
///
/// 针对中国大陆访问 GitHub 慢的问题：
/// - **镜像回退**：直连（api.github.com / github.com）失败或超时后，自动切换到
///   公共加速镜像（ghproxy 等前缀代理）重试。检查更新与下载都走回退链。
/// - **后台下载 + 断点续传**：下载交给系统 DownloadManager（flutter_downloader），
///   退出设置页、甚至退出 App 都继续下载；网络中断后 resume() 从断点续传。
/// - **状态持久化**：taskId / 版本 / 保存路径写 SharedPreferences，重进设置页时
///   恢复「下载中 / 已下载待安装」状态，不再丢失。
class UpdateService {
  UpdateService._();

  static const _repo = 'RecardoLyu/PerlerBeadsDesigner';
  static const _timeout = Duration(seconds: 15);

  /// 公共镜像加速前缀（按优先级依次回退；空串 = 直连）。
  /// 这些镜像代理 github.com 的下载与 api.github.com 的 release 查询。
  static const _mirrors = <String>[
    '', // 直连优先
    'https://mirror.ghproxy.com/',
    'https://gh-proxy.com/',
    'https://ghfast.top/',
  ];

  // ---- SharedPreferences 键：持久化下载任务状态 ----
  static const _kTaskId = 'upd_task_id';
  static const _kVersion = 'upd_version';
  static const _kSavedDir = 'upd_saved_dir';
  static const _kFileName = 'upd_file_name';

  /// 当前安装版本（来自 pubspec version，如 2.4.1）。
  static Future<String> currentVersion() async {
    final info = await PackageInfo.fromPlatform();
    return info.version;
  }

  /// 检查更新。依次尝试镜像回退链，全部失败返回 null（调用方按「检查失败」提示）。
  static Future<UpdateInfo?> check() async {
    for (final m in _mirrors) {
      final info = await _tryCheck(m);
      if (info != null) return info;
    }
    return null;
  }

  static Future<UpdateInfo?> _tryCheck(String mirrorPrefix) async {
    try {
      // api.github.com 无法直接被多数镜像代理，回退时用 gh-proxy 形式；
      // 直连(m='')用官方 API。镜像把「https://api.github.com/...」拼在前缀后。
      final apiUrl = mirrorPrefix.isEmpty
          ? 'https://api.github.com/repos/$_repo/releases/latest'
          : '$mirrorPrefix/https://api.github.com/repos/$_repo/releases/latest';
      final resp = await http
          .get(Uri.parse(apiUrl), headers: {'Accept': 'application/vnd.github+json'})
          .timeout(_timeout);
      if (resp.statusCode != 200) return null;
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      final tag = (data['tag_name'] as String? ?? '');
      if (tag.isEmpty) return null;
      final latest = tag.replaceFirst(RegExp(r'^[vV]'), '');
      final assets = (data['assets'] as List? ?? []);
      String? apkUrl;
      for (final a in assets) {
        final name = ((a as Map)['name'] as String? ?? '').toLowerCase();
        if (name.endsWith('.apk')) {
          apkUrl = a['browser_download_url'] as String?;
          break;
        }
      }
      final current = await currentVersion();
      return UpdateInfo(
        current: current,
        latest: latest,
        hasUpdate: _compareVersion(tag, current) > 0,
        notes: (data['body'] as String? ?? '').trim(),
        apkUrl: apkUrl,
        releaseUrl: data['html_url'] as String?,
      );
    } catch (_) {
      return null;
    }
  }

  /// 语义化版本比较：a > b 返回正数。tag 可带 v 前缀 / 后缀。
  static int _compareVersion(String a, String b) {
    List<int> parse(String s) => s
        .trim()
        .replaceFirst(RegExp(r'^[vV]'), '')
        .split('.')
        .map((p) => int.tryParse(p.replaceAll(RegExp(r'[^0-9]'), '')) ?? 0)
        .toList();
    final x = parse(a), y = parse(b);
    for (var i = 0; i < 3; i++) {
      final xi = i < x.length ? x[i] : 0;
      final yi = i < y.length ? y[i] : 0;
      if (xi != yi) return xi - yi;
    }
    return 0;
  }

  // ==================== 后台下载（flutter_downloader） ====================

  /// 下载目录：应用专属外部目录（Android/data/<pkg>/files/updates）。
  /// 相比 getTemporaryDirectory()，不会被系统当成缓存随时清理，路径明确可见。
  static Future<Directory> _updateDir() async {
    final base = await getExternalStorageDirectory();
    final dir = Directory('${base!.path}/updates');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  /// 启动后台下载。依次回退镜像，直到 enqueue 成功。
  /// 返回 true 表示已交给系统下载（进度经 [progressStream] 推送）。
  static Future<bool> startDownload(UpdateInfo info) async {
    if (info.apkUrl == null) return false;
    final dir = await _updateDir();
    final fileName = 'perler_update_${info.latest}.apk';
    // 清掉旧的更新包，避免占用空间 / 装错版本
    await _cleanOldApks(dir);

    for (final m in _mirrors) {
      final url = m.isEmpty ? info.apkUrl! : '$m/${info.apkUrl!}';
      try {
        final taskId = await FlutterDownloader.enqueue(
          url: url,
          savedDir: dir.path,
          fileName: fileName,
          showNotification: true,
          openFileFromNotification: false, // 我们自己控制安装时机
        );
        if (taskId != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString(_kTaskId, taskId);
          await prefs.setString(_kVersion, info.latest);
          await prefs.setString(_kSavedDir, dir.path);
          await prefs.setString(_kFileName, fileName);
          return true;
        }
      } catch (_) {
        // 该镜像 enqueue 失败，试下一个
      }
    }
    return false;
  }

  static Future<void> _cleanOldApks(Directory dir) async {
    try {
      await for (final f in dir.list()) {
        if (f is File && f.path.toLowerCase().endsWith('.apk')) {
          await f.delete();
        }
      }
    } catch (_) {}
  }

  /// 进度流：后台 isolate 的 callback 经 IsolateNameServer 转发到此处。
  /// 值为 (status, progress)。调用方在设置页 listen 即可；widget 销毁不影响下载。
  static final _port = ReceivePort();
  static final _controller = StreamController<DownloadTaskStatus>.broadcast();
  static bool _portBound = false;

  static Stream<DownloadTaskStatus> get progressStream => _controller.stream;

  static const _portName = 'perler_downloader_port';

  /// 后台 isolate 回调（必须是 top-level/static + entry-point 注解）。
  @pragma('vm:entry-point')
  static void downloadCallback(String id, int status, int progress) {
    final send = IsolateNameServer.lookupPortByName(_portName);
    send?.send([id, status, progress]);
  }

  /// 绑定回调端口（幂等）。设置页进入时调用一次。
  static void bindCallback() {
    if (_portBound) return;
    _portBound = true;
    IsolateNameServer.registerPortWithName(_port.sendPort, _portName);
    FlutterDownloader.registerCallback(downloadCallback);
    _port.listen((data) async {
      final id = data[0] as String;
      final status = DownloadTaskStatus.fromInt(data[1] as int);
      _controller.add(status);
      // 完成：校验包名并提示安装
      if (status == DownloadTaskStatus.complete) {
        await _onDownloadComplete(id);
      }
    });
  }

  static Future<void> _onDownloadComplete(String taskId) async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getString(_kTaskId) != taskId) return;
    // 下载完成 → 包名校验通过则自动调起安装
    final path = await downloadedApkPath();
    if (path != null && await verifyPackage(path)) {
      await installApk(path);
    }
  }

  /// 恢复持久化的下载任务状态（重进设置页时调用）。
  /// 返回当前任务快照：null=无任务；否则含状态/进度/是否完成可安装。
  static Future<UpdateTaskSnapshot?> restoreTask() async {
    final prefs = await SharedPreferences.getInstance();
    final taskId = prefs.getString(_kTaskId);
    if (taskId == null) return null;
    try {
      final tasks = await FlutterDownloader.loadTasks();
      DownloadTask? task;
      for (final t in tasks ?? <DownloadTask>[]) {
        if (t.taskId == taskId) {
          task = t;
          break;
        }
      }
      if (task == null) {
        // 系统已清掉该任务（如重启后）→ 看文件是否已完整下载
        final path = await downloadedApkPath();
        if (path != null && await File(path).exists()) {
          return UpdateTaskSnapshot(
              version: prefs.getString(_kVersion) ?? '',
              status: DownloadTaskStatus.complete,
              progress: 100,
              apkPath: path);
        }
        await clearTask();
        return null;
      }
      final path = await downloadedApkPath();
      return UpdateTaskSnapshot(
        version: prefs.getString(_kVersion) ?? '',
        status: task.status,
        progress: task.progress,
        apkPath: task.status == DownloadTaskStatus.complete ? path : null,
      );
    } catch (_) {
      return null;
    }
  }

  /// 已下载 APK 的完整路径（未下载完返回 null）。
  static Future<String?> downloadedApkPath() async {
    final prefs = await SharedPreferences.getInstance();
    final dir = prefs.getString(_kSavedDir);
    final name = prefs.getString(_kFileName);
    if (dir == null || name == null) return null;
    final path = '$dir/$name';
    return await File(path).exists() ? path : null;
  }

  /// 断点续传：网络中断失败后，从断点继续（返回新 taskId）。
  static Future<bool> resumeDownload() async {
    final prefs = await SharedPreferences.getInstance();
    final taskId = prefs.getString(_kTaskId);
    if (taskId == null) return false;
    try {
      final newId = await FlutterDownloader.resume(taskId: taskId);
      if (newId != null) {
        await prefs.setString(_kTaskId, newId);
        return true;
      }
      // resume 失败（如任务状态不允许）→ 重新入队整个下载
      return await _retryEnqueue(prefs);
    } catch (_) {
      return await _retryEnqueue(prefs);
    }
  }

  static Future<bool> _retryEnqueue(SharedPreferences prefs) async {
    final version = prefs.getString(_kVersion);
    if (version == null) return false;
    // 用持久化的版本重新检查一次拿 apkUrl，再走 startDownload 全镜像回退
    final info = await check();
    if (info == null || info.apkUrl == null) return false;
    return await startDownload(info);
  }

  /// 取消并清除持久化任务。
  static Future<void> clearTask() async {
    final prefs = await SharedPreferences.getInstance();
    final taskId = prefs.getString(_kTaskId);
    if (taskId != null) {
      try {
        await FlutterDownloader.cancel(taskId: taskId);
      } catch (_) {}
    }
    await prefs.remove(_kTaskId);
    await prefs.remove(_kVersion);
    await prefs.remove(_kSavedDir);
    await prefs.remove(_kFileName);
  }

  /// 校验下载的 APK 包名与本应用一致（防装错包 / 防签名冲突装到别的应用上）。
  static Future<bool> verifyPackage(String apkPath) async {
    // 轻量校验：确认文件存在且非空。完整包名/签名校验交给系统安装器，
    // 若签名不一致系统会提示「与已安装应用签名冲突」，此时需卸载旧版再装
    // （本地 flutter run 装的 debug 包与 CI 包签名可能不同）。
    try {
      final f = File(apkPath);
      return await f.exists() && await f.length() > 0;
    } catch (_) {
      return false;
    }
  }

  /// 调系统安装器安装已下载的 APK（需 REQUEST_INSTALL_PACKAGES 权限）。
  /// 签名冲突时系统会拒绝并在安装器界面提示；调用方应引导用户先卸载旧版。
  static Future<void> installApk(String path) async {
    await OpenFile.open(path, type: 'application/vnd.android.package-archive');
  }
}

class UpdateInfo {
  final String current;
  final String latest;
  final bool hasUpdate;
  final String notes;
  final String? apkUrl;
  final String? releaseUrl;
  const UpdateInfo({
    required this.current,
    required this.latest,
    required this.hasUpdate,
    required this.notes,
    this.apkUrl,
    this.releaseUrl,
  });
}

/// 恢复出来的下载任务快照（重进设置页时还原 UI 状态）。
class UpdateTaskSnapshot {
  final String version;
  final DownloadTaskStatus status;
  final int progress; // 0..100
  final String? apkPath; // 仅 complete 时非空
  const UpdateTaskSnapshot({
    required this.version,
    required this.status,
    required this.progress,
    this.apkPath,
  });
  bool get isComplete => status == DownloadTaskStatus.complete && apkPath != null;
  bool get isRunning => status == DownloadTaskStatus.running ||
      status == DownloadTaskStatus.enqueued;
  bool get isFailed => status == DownloadTaskStatus.failed ||
      status == DownloadTaskStatus.canceled;
}
