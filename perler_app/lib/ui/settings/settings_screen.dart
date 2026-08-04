import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_downloader/flutter_downloader.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../services/update_service.dart';
import '../../state/app_state.dart';
import '../../state/skin_state.dart';
import '../../theme/candy_theme.dart';
import '../widgets.dart';
import 'help_screen.dart';

/// 设置页：主题（跟随系统/浅色/深色）+ 算法默认参数 + 关于（版本号 + 使用帮助）。
/// 从顶栏「设置」按钮进入（全屏路由），替代原「帮助」入口。
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    final themeMode = ref.watch(themeModeProvider);
    final settings = ref.watch(settingsProvider);

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [c.bg, c.bg2],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // 顶栏：返回 + 标题
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 10, 16, 6),
                child: Row(children: [
                  IconButton(
                    icon: Icon(Icons.arrow_back_rounded, color: c.foreground),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                  const SizedBox(width: 4),
                  Text('设置', style: TextStyle(fontFamily: 'Fredoka', fontSize: 19, fontWeight: FontWeight.w600, color: c.foregroundStrong)),
                ]),
              ),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
                  children: [
                    _Section(c, icon: Icons.dark_mode_rounded, title: '外观', child: _ThemePicker(mode: themeMode)),
                    _Section(c, icon: Icons.palette_rounded, title: '自定义主题', child: const _SkinCard()),
                    _Section(c, icon: Icons.grid_on_rounded, title: '图纸默认参数', child: _PatternDefaults(settings: settings)),
                    _Section(c, icon: Icons.content_cut_rounded, title: '分割默认参数', child: _SegmentDefaults(settings: settings)),
                    _Section(c, icon: Icons.info_outline_rounded, title: '关于', child: const _About()),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final CandyTheme c;
  final IconData icon;
  final String title;
  final Widget child;
  const _Section(this.c, {required this.icon, required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: BoxDecoration(
        color: c.surface,
        border: Border.all(color: c.border),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 16, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 7),
          Text(title, style: TextStyle(fontFamily: 'Fredoka', fontSize: 15, fontWeight: FontWeight.w600, color: c.foregroundStrong)),
        ]),
        const SizedBox(height: 10),
        child,
      ]),
    );
  }
}

/// 主题三选：跟随系统 / 浅色 / 深色
class _ThemePicker extends ConsumerWidget {
  final ThemeMode mode;
  const _ThemePicker({required this.mode});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    Widget opt(ThemeMode m, IconData icon, String label) {
      final on = mode == m;
      return Expanded(
        child: GestureDetector(
          onTap: () => ref.read(themeModeProvider.notifier).set(m),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              gradient: on ? candyPrimaryGradient(context) : null,
              color: on ? null : c.muted,
              border: on ? null : Border.all(color: c.border),
              borderRadius: BorderRadius.circular(15),
            ),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icon, size: 20, color: on ? Colors.white : c.mutedFg),
              const SizedBox(height: 5),
              Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: on ? Colors.white : c.mutedFg)),
            ]),
          ),
        ),
      );
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        opt(ThemeMode.system, Icons.brightness_auto_rounded, '跟随系统'),
        const SizedBox(width: 8),
        opt(ThemeMode.light, Icons.light_mode_rounded, '浅色'),
        const SizedBox(width: 8),
        opt(ThemeMode.dark, Icons.dark_mode_rounded, '深色'),
      ]),
      const SizedBox(height: 8),
      Text('「跟随系统」时随手机系统的浅色/深色模式自动切换。',
          style: TextStyle(fontSize: 11, color: c.mutedFg)),
    ]);
  }
}

/// 背景皮肤卡片：导入图片作半透明模糊壁纸 + 自动提取主体色换主题色（免重启即时生效）。
/// 与桌面端设置中心「背景皮肤」卡片对应。
class _SkinCard extends ConsumerWidget {
  const _SkinCard();

  Future<void> _pick(BuildContext context, WidgetRef ref) async {
    final c = context.candy;
    final src = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: c.surfaceStrong,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(22)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('从相册选择'),
              onTap: () => Navigator.pop(ctx, 'gallery'),
            ),
            ListTile(
              leading: const Icon(Icons.folder_open_outlined),
              title: const Text('从文件选择'),
              subtitle: const Text('jpg / png / bmp / webp'),
              onTap: () => Navigator.pop(ctx, 'file'),
            ),
          ],
        ),
      ),
    );
    if (src == null) return;
    final notifier = ref.read(skinProvider.notifier);
    try {
      if (src == 'gallery') {
        await notifier.importFromGallery();
      } else {
        await notifier.importFromFile();
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('皮肤导入失败，请换一张图片试试')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    final skin = ref.watch(skinProvider);

    final colorHex = skin.colorValue == null
        ? null
        : '#${skin.colorValue!.toRadixString(16).padLeft(6, '0').toUpperCase()}';

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        // 缩略图
        Container(
          width: 62,
          height: 62,
          decoration: BoxDecoration(
            color: c.muted,
            border: Border.all(color: c.border),
            borderRadius: BorderRadius.circular(14),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(13),
            // 壁纸路径恒定，用自增 version 作 key 强制刷新（同 SkinBackdrop）
            child: skin.enabled && skin.wallpaperPath != null
                ? Image.file(File(skin.wallpaperPath!),
                    key: ValueKey('${skin.wallpaperPath}@v${skin.version}'),
                    fit: BoxFit.cover)
                : Icon(Icons.image_outlined, size: 26, color: c.mutedFg),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(children: [
            InkWell(
              onTap: skin.busy ? null : () => _pick(context, ref),
              borderRadius: BorderRadius.circular(14),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 11),
                decoration: BoxDecoration(
                  gradient: candyPrimaryGradient(context),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  if (skin.busy)
                    const SizedBox(
                        width: 15, height: 15,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                  else
                    const Icon(Icons.add_photo_alternate_outlined,
                        size: 17, color: Colors.white),
                  const SizedBox(width: 7),
                  Text(skin.enabled ? '更换图片' : '导入图片',
                      style: const TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white)),
                ]),
              ),
            ),
            if (skin.enabled) ...[
              const SizedBox(height: 6),
              InkWell(
                onTap: skin.busy ? null : () => ref.read(skinProvider.notifier).remove(),
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  decoration: BoxDecoration(
                    color: c.muted,
                    border: Border.all(color: c.border),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.delete_outline_rounded, size: 16, color: c.foregroundStrong),
                    const SizedBox(width: 6),
                    Text('移除主题',
                        style: TextStyle(
                            fontSize: 12.5, fontWeight: FontWeight.w700, color: c.foregroundStrong)),
                  ]),
                ),
              ),
            ],
          ]),
        ),
      ]),
      const SizedBox(height: 8),
      // 提示：识别到的主体色 / 未识别
      if (skin.enabled)
        Row(children: [
          if (colorHex != null) ...[
            Container(
              width: 14, height: 14,
              decoration: BoxDecoration(
                color: Color(0xFF000000 | skin.colorValue!),
                border: Border.all(color: c.border),
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(width: 6),
            Text('已识别主体颜色 $colorHex，主题色已跟随更换。',
                style: TextStyle(fontSize: 11, color: c.mutedFg)),
          ] else
            Text('未识别到主体颜色，仅更换了背景。',
                style: TextStyle(fontSize: 11, color: c.mutedFg)),
        ])
      else
        Text('导入图片作半透明背景，并自动提取主体颜色定制整套主题色。',
            style: TextStyle(fontSize: 11, height: 1.4, color: c.mutedFg)),
      // 不透明度滑杆（亮暗共用单一值）+ 模糊三档（吸附）
      if (skin.enabled) ...[
        const SizedBox(height: 4),
        SliderRow(
          label: '背景不透明度',
          value: skin.opacity * 100,
          min: 5, max: 40, decimals: 0,
          onChanged: (v) => ref.read(skinProvider.notifier).setOpacity(v / 100),
        ),
        const SizedBox(height: 4),
        Row(children: [
          SizedBox(width: 76,
              child: Text('背景模糊',
                  style: TextStyle(fontSize: 12, color: c.mutedFg))),
          Expanded(
            child: Slider(
              value: skin.blurLevel.toDouble(),
              min: 0, max: 2, divisions: 2,
              onChanged: (v) =>
                  ref.read(skinProvider.notifier).setBlurLevel(v.round()),
            ),
          ),
          SizedBox(width: 44,
              child: Text(const ['无', '中', '高'][skin.blurLevel],
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                      color: c.foregroundStrong))),
        ]),
      ],
    ]);
  }
}

class _PatternDefaults extends ConsumerWidget {
  final AppSettings settings;
  const _PatternDefaults({required this.settings});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    final set = ref.read(settingsProvider.notifier);
    return Column(children: [
      Row(children: [
        SizedBox(width: 88, child: Text('默认宽度(豆)', style: TextStyle(fontSize: 12.5, color: c.mutedFg))),
        Expanded(child: TextFormField(
          key: ValueKey('w${settings.defWidth}'),
          initialValue: settings.defWidth.toString(),
          keyboardType: TextInputType.number,
          onChanged: (s) => set.state = settings.copyWith(defWidth: (int.tryParse(s) ?? settings.defWidth).clamp(1, 512)),
        )),
      ]),
      const SizedBox(height: 6),
      Row(children: [
        SizedBox(width: 88, child: Text('颜色上限', style: TextStyle(fontSize: 12.5, color: c.mutedFg))),
        Expanded(child: TextFormField(
          key: ValueKey('c${settings.maxColors}'),
          initialValue: settings.maxColors.toString(),
          keyboardType: TextInputType.number,
          onChanged: (s) => set.state = settings.copyWith(maxColors: (int.tryParse(s) ?? 0).clamp(0, 221)),
        )),
        const SizedBox(width: 8),
        Text('0=不限', style: TextStyle(fontSize: 11, color: c.mutedFg)),
      ]),
      SliderRow(label: '细节保留', value: settings.salience, min: 0, max: 2, decimals: 1,
          onChanged: (v) => set.state = settings.copyWith(salience: v)),
      SelectRow<String>(label: '颜色度量', value: settings.metric, items: const [
        ('weighted', '加权距离'), ('euclidean', '欧氏距离'), ('lab', 'Lab色空'), ('ciede76', 'CIE76'), ('ciede2000', 'CIEDE2000'),
      ], onChanged: (v) => set.state = settings.copyWith(metric: v)),
      CheckRow(label: '默认保持图像比例', value: settings.keepRatio,
          onChanged: (v) => set.state = settings.copyWith(keepRatio: v)),
      CheckRow(label: '默认开启抖动', value: settings.dither,
          onChanged: (v) => set.state = settings.copyWith(dither: v)),
      CheckRow(label: '默认开启高阶优化(ICM)', value: settings.icm,
          onChanged: (v) => set.state = settings.copyWith(icm: v)),
    ]);
  }
}

class _SegmentDefaults extends ConsumerWidget {
  final AppSettings settings;
  const _SegmentDefaults({required this.settings});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final set = ref.read(settingsProvider.notifier);
    return Column(children: [
      SelectRow<String>(label: '默认方法', value: settings.segMethod, items: const [
        ('grabcut_rect', 'GrabCut矩形'), ('watershed', '分水岭'), ('otsu', 'Otsu'), ('slic', 'SLIC'),
      ], onChanged: (v) => set.state = settings.copyWith(segMethod: v)),
      SliderRow(label: '笔触粗细', value: settings.brushSize, min: 4, max: 40, decimals: 0,
          onChanged: (v) => set.state = settings.copyWith(brushSize: v)),
    ]);
  }
}

/// 关于：版本号 + 使用帮助（吸收原「帮助」入口）+ 检查更新/在线更新。
class _About extends StatefulWidget {
  const _About();

  @override
  State<_About> createState() => _AboutState();
}

class _AboutState extends State<_About> {
  String _version = '…';
  bool _checking = false;
  double? _progress;          // null=未在下载；0..1=下载中
  UpdateInfo? _info;
  String _status = '';
  bool _downloaded = false;
  String? _apkPath;
  bool _failed = false;       // 下载失败（可断点续传）
  StreamSubscription<DownloadTaskStatus>? _sub;
  Timer? _pollTimer;          // 下载中周期性拉系统任务进度刷新 UI

  @override
  void initState() {
    super.initState();
    UpdateService.currentVersion()
        .then((v) => mounted ? setState(() => _version = v) : null);
    // 绑定后台下载回调（幂等），并恢复持久化的任务状态：
    // 退出设置页/重启 App 后，下载仍在系统 DownloadManager 里跑，
    // 这里重进时把「下载中 / 已下载待安装」状态还原回来。
    UpdateService.bindCallback();
    _sub = UpdateService.progressStream.listen(_onTaskStatus);
    _restore();
  }

  /// 启动/停止进度轮询：下载进行中每 800ms 拉一次系统任务进度。
  void _syncPolling() {
    final need = _progress != null;
    if (need && _pollTimer == null) {
      _pollTimer = Timer.periodic(const Duration(milliseconds: 800), (_) async {
        final snap = await UpdateService.restoreTask();
        if (!mounted) return;
        if (snap != null && snap.isRunning) {
          setState(() => _progress = snap.progress / 100);
        }
      });
    } else if (!need) {
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  Future<void> _restore() async {
    final snap = await UpdateService.restoreTask();
    if (!mounted || snap == null) return;
    setState(() {
      if (snap.isComplete) {
        _downloaded = true;
        _apkPath = snap.apkPath;
        _progress = null;
        _failed = false;
        _status = 'v${snap.version} 已下载完成，点击安装';
      } else if (snap.isRunning) {
        _progress = snap.progress / 100;
        _failed = false;
        _status = '正在后台下载 v${snap.version}（退出本页不会中断）';
      } else if (snap.isFailed) {
        _progress = null;
        _failed = true;
        _status = '下载中断，点击「继续下载」从断点续传';
      }
    });
    _syncPolling();
  }

  void _onTaskStatus(DownloadTaskStatus status) async {
    if (!mounted) return;
    if (status == DownloadTaskStatus.complete) {
      final path = await UpdateService.downloadedApkPath();
      if (!mounted) return;
      setState(() {
        _progress = null;
        _failed = false;
        _downloaded = path != null;
        _apkPath = path;
        _status = path != null ? '下载完成，点击安装' : '下载完成但文件缺失，请重试';
      });
      _syncPolling();
    } else if (status == DownloadTaskStatus.failed ||
        status == DownloadTaskStatus.canceled) {
      setState(() {
        _progress = null;
        _failed = true;
        _status = '下载中断，点击「继续下载」从断点续传';
      });
      _syncPolling();
    }
  }

  Future<void> _check() async {
    setState(() { _checking = true; _status = '正在检查更新…'; _info = null; _downloaded = false; _failed = false; });
    final info = await UpdateService.check();
    if (!mounted) return;
    setState(() {
      _checking = false;
      _info = info;
      if (info == null) {
        _status = '检查失败：GitHub 与各镜像均无法访问，请检查网络后重试';
      } else if (info.hasUpdate) {
        _status = info.apkUrl != null
            ? '发现新版本 v${info.latest}（当前 v${info.current}）'
            : '发现新版本 v${info.latest}，但未找到安装包';
      } else {
        _status = '已是最新版本（v${info.current}）';
      }
    });
  }

  /// 开始后台下载（原生 DownloadManager）。退出本页/锁屏/退到后台都继续。
  Future<void> _download() async {
    final info = _info;
    if (info?.apkUrl == null) return;
    setState(() { _progress = 0; _failed = false; _status = '启动后台下载…'; });
    _syncPolling();
    final ok = await UpdateService.startDownload(info!);
    if (!mounted) return;
    if (ok) {
      setState(() => _status = '正在后台下载 v${info.latest}（可退出本页，通知栏看进度）');
    } else {
      setState(() { _progress = null; _status = '下载启动失败：GitHub 与各镜像均无法连接'; });
    }
    _syncPolling();
  }

  /// 断点续传。
  Future<void> _resume() async {
    setState(() { _progress = 0; _failed = false; _status = '从断点继续下载…'; });
    _syncPolling();
    final ok = await UpdateService.resumeDownload();
    if (!mounted) return;
    if (!ok) {
      setState(() { _progress = null; _status = '续传失败，请重新下载'; });
    }
    _syncPolling();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final info = _info;
    final showUpdate = info != null && info.hasUpdate && info.apkUrl != null;
    final downloading = _progress != null;

    // 主按钮的文案与动作
    final String label;
    final IconData icon;
    final VoidCallback? action;
    if (_checking) {
      label = '检查中…'; icon = Icons.system_update_alt_rounded; action = null;
    } else if (downloading) {
      label = '后台下载中…'; icon = Icons.downloading_rounded; action = null;
    } else if (_failed) {
      label = '继续下载（断点续传）'; icon = Icons.refresh_rounded; action = _resume;
    } else if (_downloaded && _apkPath != null) {
      label = '安装更新'; icon = Icons.install_mobile_rounded;
      action = () => UpdateService.installApk(_apkPath!);
    } else if (showUpdate) {
      label = '下载并更新到 v${info.latest}'; icon = Icons.download_rounded;
      action = _download;
    } else {
      label = '检查更新'; icon = Icons.system_update_alt_rounded; action = _check;
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text('拼豆图纸生成器', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: c.foregroundStrong)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
          decoration: BoxDecoration(color: c.muted, border: Border.all(color: c.border), borderRadius: BorderRadius.circular(999)),
          child: Text('v$_version 移动版', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: c.mutedFg)),
        ),
      ]),
      const SizedBox(height: 12),
      // 呼出完整使用指南（全屏帮助文档）
      InkWell(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const HelpScreen()),
        ),
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            gradient: candyPrimaryGradient(context),
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Row(children: [
            Icon(Icons.menu_book_rounded, size: 18, color: Colors.white),
            SizedBox(width: 9),
            Expanded(
              child: Text('查看使用指南',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white)),
            ),
            Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Colors.white),
          ]),
        ),
      ),
      const SizedBox(height: 10),
      // 检查更新 / 后台下载 / 断点续传 / 安装
      InkWell(
        onTap: action,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: c.muted,
            border: Border.all(color: c.border),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(children: [
            Icon(icon, size: 18, color: c.foregroundStrong),
            const SizedBox(width: 9),
            Expanded(
              child: Text(label,
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: c.foregroundStrong)),
            ),
            if (_checking || downloading)
              SizedBox(width: 16, height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2,
                      value: downloading ? _progress : null,
                      color: Theme.of(context).colorScheme.primary))
            else
              Icon(Icons.arrow_forward_ios_rounded, size: 14, color: c.mutedFg),
          ]),
        ),
      ),
      if (downloading) ...[
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: LinearProgressIndicator(value: _progress, minHeight: 6,
              backgroundColor: c.muted, color: Theme.of(context).colorScheme.primary),
        ),
      ],
      if (_status.isNotEmpty) ...[
        const SizedBox(height: 8),
        Text(_status, style: TextStyle(fontSize: 11, height: 1.4, color: c.mutedFg)),
        if (showUpdate && info.notes.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(info.notes.length > 200 ? '${info.notes.substring(0, 200)}…' : info.notes,
                style: TextStyle(fontSize: 10.5, height: 1.4, color: c.mutedFg)),
          ),
      ],
    ]);
  }
}
