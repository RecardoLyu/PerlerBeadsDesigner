import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'theme/candy_theme.dart';
import 'theme/skin.dart';
import 'state/app_state.dart';
import 'state/skin_state.dart';
import 'ui/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
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
