import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:open_file/open_file.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';

/// 在线更新（Android）：检查 GitHub Release 最新版本 → 后台下载 APK →
/// 调系统安装器安装。与桌面端共用同一仓库的 Release。
///
/// CI 在 `v*.*.*` tag 推送时把 `PerlerBeads-debug-vX.Y.Z.apk` 传到 Release，
/// 此处匹配以 `.apk` 结尾的 asset（同一 Release 内 APK 只有一个）。
class UpdateService {
  UpdateService._();

  static const _repo = 'RecardoLyu/PerlerBeadsDesigner';
  static const _api = 'https://api.github.com/repos/$_repo/releases/latest';
  static const _timeout = Duration(seconds: 20);

  /// 当前安装版本（来自 pubspec version，如 2.3.0）。
  static Future<String> currentVersion() async {
    final info = await PackageInfo.fromPlatform();
    return info.version;
  }

  /// 检查更新。返回 null 表示请求失败（调用方按「检查失败」提示）。
  static Future<UpdateInfo?> check() async {
    try {
      final resp = await http
          .get(Uri.parse(_api), headers: {'Accept': 'application/vnd.github+json'})
          .timeout(_timeout);
      if (resp.statusCode != 200) return null;
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      final tag = (data['tag_name'] as String? ?? '');
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

  /// 下载 APK 到临时目录，[onProgress] 回调 0..1（无 Content-Length 时只回调完成）。
  /// 返回本地文件路径；失败抛异常。
  static Future<String> downloadApk(String url,
      {void Function(double)? onProgress}) async {
    final req = http.Request('GET', Uri.parse(url));
    final resp = await http.Client().send(req).timeout(_timeout);
    if (resp.statusCode != 200) {
      throw Exception('下载失败 HTTP ${resp.statusCode}');
    }
    final total = resp.contentLength ?? 0;
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/perler_update.apk');
    final sink = file.openWrite();
    var got = 0;
    await for (final chunk in resp.stream) {
      sink.add(chunk);
      got += chunk.length;
      if (total > 0 && onProgress != null) onProgress(got / total);
    }
    await sink.flush();
    await sink.close();
    return file.path;
  }

  /// 调系统安装器安装已下载的 APK（需 REQUEST_INSTALL_PACKAGES 权限）。
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
