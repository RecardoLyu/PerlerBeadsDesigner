import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_downloader/flutter_downloader.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'theme/candy_theme.dart';
import 'theme/skin.dart';
import 'services/update_service.dart';
import 'state/app_state.dart';
import 'state/skin_state.dart';
import 'ui/home_screen.dart';

Future<void> main() async {
  // runZonedGuarded 兜底：任何未捕获异常都记录日志，不让 App 启动即崩。
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();
    // 在线更新：原生 DownloadManager 后台下载（退出页面/App 不中断、断点续传）。
    // 必须在 runApp 前初始化。包 try/catch：初始化失败时仅降级「在线更新不可用」，
    // 不阻塞 runApp（否则原生层一抛异常 App 就直接闪退）。
    try {
      await FlutterDownloader.initialize(debug: false, ignoreSsl: false);
      // callback 在 main() 立即注册（官方示例约定），避免冷启动时原生回调未注册句柄。
      FlutterDownloader.registerCallback(UpdateService.downloadCallback);
    } catch (e) {
      // 降级：更新功能不可用，但 App 正常启动
      debugPrint('FlutterDownloader 初始化失败（在线更新将不可用）: $e');
    }
    // 启动前先恢复主题模式与皮肤，override 注入初始值，防闪一下默认粉再跳变
    final initialThemeMode = await SkinNotifier.restoreThemeMode();
    final initialSkin = await SkinNotifier.restore();
    runApp(ProviderScope(
      overrides: [
        themeModeProvider.overrideWith((_) => ThemeModeNotifier(initialThemeMode)),
        skinProvider.overrideWith((_) => SkinNotifier(initialSkin)),
      ],
      child: const PerlerApp(),
    ));
  }, (error, stack) {
    debugPrint('未捕获异常: $error\n$stack');
  });
}

class PerlerApp extends ConsumerWidget {
  const PerlerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    final skin = ref.watch(skinProvider);

    // 皮肤启用且有主体色 → 亮/暗各推导一套主题色（含辅助色调和）；否则走默认糖果主题
    SkinPalette? palLight, palDark;
    final cv = skin.colorValue;
    if (skin.enabled && cv != null) {
      final base = Color(0xFF000000 | cv);
      final accent =
          skin.accentValue != null ? Color(0xFF000000 | skin.accentValue!) : null;
      palLight = deriveSkinPalette(base, Brightness.light, accent: accent);
      palDark = deriveSkinPalette(base, Brightness.dark, accent: accent);
    }

    return MaterialApp(
      title: '拼豆图纸生成器',
      debugShowCheckedModeBanner: false,
      theme: buildCandyTheme(Brightness.light, skin: palLight),
      darkTheme: buildCandyTheme(Brightness.dark, skin: palDark),
      themeMode: mode,
      // 壁纸层覆盖所有路由：实色打底 → 半透明壁纸（按档实时模糊）→ 页面
      // （页面渐变经扩展 bg/bg2 的 alpha 自动变薄，壁纸透出来）
      builder: (context, child) => SkinBackdrop(
        enabled: skin.enabled && skin.wallpaperPath != null,
        wallpaperPath: skin.wallpaperPath,
        opacity: skin.opacity,
        blurLevel: skin.blurLevel,
        version: skin.version,
        child: child ?? const SizedBox.shrink(),
      ),
      home: const HomeScreen(),
    );
  }
}
