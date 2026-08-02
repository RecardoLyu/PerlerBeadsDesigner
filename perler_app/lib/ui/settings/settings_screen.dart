import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../state/app_state.dart';
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
              gradient: on ? candyPrimaryGradient(Theme.of(context).brightness) : null,
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

/// 关于：版本号 + 使用帮助（吸收原「帮助」入口）。
class _About extends StatelessWidget {
  const _About();

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text('拼豆图纸生成器', style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: c.foregroundStrong)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
          decoration: BoxDecoration(color: c.muted, border: Border.all(color: c.border), borderRadius: BorderRadius.circular(999)),
          child: Text('v2.1.0 移动版', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: c.mutedFg)),
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
            gradient: candyPrimaryGradient(Theme.of(context).brightness),
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
      Text('从加载图像、分割抠图到生成拼豆图纸、导出的完整操作说明与常见问题。',
          style: TextStyle(fontSize: 11, height: 1.45, color: c.mutedFg)),
    ]);
  }
}
