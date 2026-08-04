import 'dart:io';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/painting.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../theme/skin.dart';

/// 皮肤状态（壁纸路径 + 主/辅色 + 共用不透明度 + 模糊档 + 版本号）。
class SkinState {
  final bool enabled;
  final int? colorValue; // 0xRRGGBB 主色；null=未识别到（只换背景）
  final int? accentValue; // 0xRRGGBB 辅助色（第二彩色簇）；null=无
  final double opacity; // 亮暗共用的单一不透明度
  final int blurLevel; // 模糊档 0=无/1=中/2=高
  final String? wallpaperPath;
  final int version; // 导入版本号：自增，驱动壁纸/缩略图强制刷新
  final bool busy; // 导入处理中

  const SkinState({
    this.enabled = false,
    this.colorValue,
    this.accentValue,
    this.opacity = 0.15,
    this.blurLevel = 1,
    this.wallpaperPath,
    this.version = 0,
    this.busy = false,
  });

  SkinState copyWith({
    bool? enabled,
    int? colorValue,
    int? accentValue,
    bool clearColor = false,
    double? opacity,
    int? blurLevel,
    String? wallpaperPath,
    int? version,
    bool? busy,
  }) =>
      SkinState(
        enabled: enabled ?? this.enabled,
        colorValue: clearColor ? null : (colorValue ?? this.colorValue),
        accentValue: clearColor ? null : (accentValue ?? this.accentValue),
        opacity: opacity ?? this.opacity,
        blurLevel: blurLevel ?? this.blurLevel,
        wallpaperPath: wallpaperPath ?? this.wallpaperPath,
        version: version ?? this.version,
        busy: busy ?? this.busy,
      );
}

/// 皮肤状态管理：导入（compute 预处理）→ 落盘 → 取色 → prefs 持久化。
/// 与桌面端 settings.json 的 skinImage/skinColor/skinOpacity/skinBlur 对应。
class SkinNotifier extends StateNotifier<SkinState> {
  SkinNotifier(super.initial);

  static const _kEnabled = 'skin.enabled';
  static const _kColor = 'skin.color';
  static const _kAccent = 'skin.accent';
  static const _kOpacity = 'skin.opacity';
  static const _kBlur = 'skin.blurLevel';
  static const _kOpL = 'skin.opacityLight';   // 旧键（迁移用）
  static const _kOpD = 'skin.opacityDark';    // 旧键（迁移用）
  static const _kThemeMode = 'themeMode';

  static Future<File> _wallpaperFile() async {
    final dir = await getApplicationSupportDirectory();
    return File('${dir.path}${Platform.pathSeparator}skin_wallpaper.jpg');
  }

  /// 启动恢复：读 prefs + 探测壁纸文件（main() 中 runApp 前调用）。
  /// 配置说启用但文件缺失 → 回写 prefs 清除，不带病启动。
  static Future<SkinState> restore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (!(prefs.getBool(_kEnabled) ?? false)) return const SkinState();
      final f = await _wallpaperFile();
      if (!await f.exists()) {
        await prefs.setBool(_kEnabled, false);
        return const SkinState();
      }
      return SkinState(
        enabled: true,
        colorValue: prefs.getInt(_kColor),
        accentValue: prefs.getInt(_kAccent),
        opacity: _readOpacity(prefs),
        blurLevel: (prefs.getInt(_kBlur) ?? 1).clamp(0, 2),
        wallpaperPath: f.path,
      );
    } catch (_) {
      return const SkinState();
    }
  }

  /// 读共用不透明度：新键优先，旧 skin.opacityLight/Dark 按当前平台亮度迁移。
  static double _readOpacity(SharedPreferences prefs) {
    final v = prefs.getDouble(_kOpacity);
    if (v != null) return v;
    final dark =
        WidgetsBinding.instance.platformDispatcher.platformBrightness ==
            Brightness.dark;
    return prefs.getDouble(dark ? _kOpD : _kOpL) ?? (dark ? 0.25 : 0.15);
  }

  /// 主题模式持久化（顺带补齐移动端既有缺口）
  static Future<ThemeMode> restoreThemeMode() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      switch (prefs.getString(_kThemeMode)) {
        case 'light':
          return ThemeMode.light;
        case 'dark':
          return ThemeMode.dark;
        default:
          return ThemeMode.system;
      }
    } catch (_) {
      return ThemeMode.system;
    }
  }

  static Future<void> persistThemeMode(ThemeMode m) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kThemeMode, switch (m) {
        ThemeMode.light => 'light',
        ThemeMode.dark => 'dark',
        ThemeMode.system => 'system',
      });
    } catch (_) { /* 静默 */ }
  }

  /// 从相册导入（maxWidth 2560 限流，超大图 picker 层先缩一道）
  Future<void> importFromGallery() async {
    try {
      final x = await ImagePicker()
          .pickImage(source: ImageSource.gallery, maxWidth: 2560);
      if (x == null) return;
      await _importBytes(await x.readAsBytes());
    } catch (_) {
      state = state.copyWith(busy: false);
    }
  }

  /// 从文件系统导入
  Future<void> importFromFile() async {
    try {
      final res = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['jpg', 'jpeg', 'png', 'bmp', 'webp'],
        withData: true,
      );
      if (res == null || res.files.isEmpty) return;
      final f = res.files.first;
      Uint8List? bytes = f.bytes;
      if (bytes == null && f.path != null) {
        bytes = await XFile(f.path!).readAsBytes();
      }
      if (bytes == null) return;
      await _importBytes(bytes);
    } catch (_) {
      state = state.copyWith(busy: false);
    }
  }

  Future<void> _importBytes(Uint8List bytes) async {
    state = state.copyWith(busy: true);
    try {
      // isolate 里一次性做：缩放 + 取色（主+辅）+ JPEG 编码（无模糊）
      final result = await compute(prepareSkinBytes, bytes);
      final f = await _wallpaperFile();
      await f.writeAsBytes(result.wallpaper, flush: true);
      // 路径恒定，主动逐出旧缓存 + 自增版本号，双保险保证多次导入即时刷新
      try {
        await FileImage(f).evict();
        PaintingBinding.instance.imageCache.clear();
      } catch (_) { /* 静默 */ }
      final primary = result.colors.isNotEmpty ? result.colors[0] : null;
      final accent = result.colors.length > 1 ? result.colors[1] : null;
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kEnabled, true);
      if (primary != null) {
        await prefs.setInt(_kColor, primary);
      } else {
        await prefs.remove(_kColor);
      }
      if (accent != null) {
        await prefs.setInt(_kAccent, accent);
      } else {
        await prefs.remove(_kAccent);
      }
      state = SkinState(
        enabled: true,
        colorValue: primary,
        accentValue: accent,
        opacity: state.opacity,
        blurLevel: state.blurLevel,
        wallpaperPath: f.path,
        version: state.version + 1,
      );
    } catch (_) {
      state = state.copyWith(busy: false);
      rethrow;
    }
  }

  /// 移除皮肤：清 prefs + 删文件（透明度/模糊记忆保留）
  Future<void> remove() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kEnabled, false);
      await prefs.remove(_kColor);
      await prefs.remove(_kAccent);
      final f = await _wallpaperFile();
      if (await f.exists()) await f.delete();
      try {
        await FileImage(f).evict();
      } catch (_) { /* 静默 */ }
    } catch (_) { /* 静默 */ }
    state = SkinState(
      opacity: state.opacity,
      blurLevel: state.blurLevel,
      version: state.version + 1,
    );
  }

  /// 调节不透明度（即时生效 + 持久化；亮暗共用单一值）
  Future<void> setOpacity(double v) async {
    final nv = v.clamp(0.05, 0.40);
    state = state.copyWith(opacity: nv);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setDouble(_kOpacity, nv);
    } catch (_) { /* 静默 */ }
  }

  /// 调节模糊档（即时生效 + 持久化；0=无/1=中/2=高）
  Future<void> setBlurLevel(int level) async {
    final nl = level.clamp(0, 2);
    state = state.copyWith(blurLevel: nl);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_kBlur, nl);
    } catch (_) { /* 静默 */ }
  }
}

/// initial 由 main() 预加载后 override 注入（防启动闪默认主题）。
final skinProvider = StateNotifierProvider<SkinNotifier, SkinState>(
    (_) => SkinNotifier(const SkinState()));
