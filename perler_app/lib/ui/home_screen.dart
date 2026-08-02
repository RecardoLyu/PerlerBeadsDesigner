import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/candy_theme.dart';
import '../../state/app_state.dart';
import 'canvas/canvas_area.dart';
import 'sheet/function_sheet.dart';

/// 主界面：顶部精简栏 + 画布（上）+ Bottom Sheet 功能栏（下）
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    final themeMode = ref.watch(themeModeProvider);

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [c.bg, c.bg2],
          ),
        ),
        child: SafeArea(
          child: Stack(
            children: [
              // 漂浮 blob 背景
              const _Blob(top: -120, left: -120, size: 420, color: Color(0xFFFB7185)),
              const _Blob(bottom: -140, right: -100, size: 380, color: Color(0xFFA78BFA)),

              Column(
                children: [
                  _TopBar(
                    isDark: themeMode == ThemeMode.dark,
                    onToggleTheme: () => ref.read(themeModeProvider.notifier).toggle(),
                  ),
                  const _StatusLine(),
                  const Expanded(child: CanvasArea()),
                ],
              ),

              // 底部功能栏（Bottom Sheet 抽屉，覆盖在画布下方）
              const FunctionSheet(),
            ],
          ),
        ),
      ),
    );
  }
}

class _Blob extends StatelessWidget {
  final double? top, bottom, left, right;
  final double size;
  final Color color;
  const _Blob({this.top, this.bottom, this.left, this.right, required this.size, required this.color});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Positioned(
      top: top, bottom: bottom, left: left, right: right,
      child: IgnorePointer(
        child: Container(
          width: size, height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withOpacity(dark ? 0.30 : 0.5),
          ),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 70, sigmaY: 70),
            child: const SizedBox.expand(),
          ),
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  final bool isDark;
  final VoidCallback onToggleTheme;
  const _TopBar({required this.isDark, required this.onToggleTheme});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
      child: Row(
        children: [
          Icon(Icons.grid_on_rounded, size: 26, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 9),
          Text('拼豆图纸生成器',
              style: TextStyle(fontFamily: 'Fredoka', fontSize: 17, fontWeight: FontWeight.w600, color: c.foregroundStrong)),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
            decoration: BoxDecoration(color: c.muted, border: Border.all(color: c.border), borderRadius: BorderRadius.circular(999)),
            child: Text('v2 移动版', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: c.mutedFg)),
          ),
          const Spacer(),
          _IconBtn(icon: isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded, onTap: onToggleTheme, tooltip: '切换主题'),
          const SizedBox(width: 9),
          _IconBtn(icon: Icons.help_outline_rounded, onTap: () {}, tooltip: '帮助'),
        ],
      ),
    );
  }
}

class _IconBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final String tooltip;
  const _IconBtn({required this.icon, required this.onTap, required this.tooltip});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 38, height: 38,
          decoration: BoxDecoration(color: c.surface, border: Border.all(color: c.border), borderRadius: BorderRadius.circular(13)),
          child: Icon(icon, size: 18, color: c.foreground),
        ),
      ),
    );
  }
}

class _StatusLine extends ConsumerWidget {
  const _StatusLine();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    final msg = ref.watch(statusMessageProvider);
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 8),
      child: Row(
        children: [
          Container(width: 7, height: 7, decoration: const BoxDecoration(shape: BoxShape.circle, color: Color(0xFF16A34A))),
          const SizedBox(width: 8),
          // 忙碌指示（颜文字 + 跳动省略号）放绿点右侧、状态文案左边的空处
          const _BusyIndicator(),
          Expanded(child: Text(msg, style: TextStyle(fontSize: 11.5, color: c.mutedFg), overflow: TextOverflow.ellipsis)),
        ],
      ),
    );
  }
}

/// 忙碌指示：桌面版同款颜文字（1s 轮换 + 上下浮动）+ 跳动省略号。
/// 仅在 busyProvider == true 时可见，让长任务期间界面不「卡死」而是有反馈。
class _BusyIndicator extends ConsumerStatefulWidget {
  const _BusyIndicator();
  @override
  ConsumerState<_BusyIndicator> createState() => _BusyIndicatorState();
}

class _BusyIndicatorState extends ConsumerState<_BusyIndicator>
    with SingleTickerProviderStateMixin {
  // 桌面版 busy 颜文字集合（src/webapp/static/js/shell.js KAOMOJI.busy）
  static const _kaomoji = [
    '(◕‿◕)', '(｡♥‿♥｡)', '(≧◡≦)', '(ﾉ◕ヮ◕)ﾉ', '(◠‿◠)',
    '(✿◠‿◠)', '(¬‿¬)', '(☆▽☆)', '(ღ˘⌣˘ღ)', '(∩^o^)⊃',
  ];
  late final AnimationController _ctl;
  int _tick = 0;

  @override
  void initState() {
    super.initState();
    // 600ms 一拍；每拍换一个颜文字 + 递进省略号 + 上下浮动。
    // 用 _tick 计数（而非相位换算），保证每帧颜文字必然不同、肉眼明显跳动。
    _ctl = AnimationController(vsync: this, duration: const Duration(milliseconds: 600))
      ..addListener(() {
        setState(() => _tick++);
      })
      ..repeat();
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(busyProvider);
    if (!busy) return const SizedBox.shrink();
    final accent = Theme.of(context).colorScheme.primary;
    return Padding(
      padding: const EdgeInsets.only(right: 7),
      child: AnimatedBuilder(
        animation: _ctl,
        builder: (_, __) {
          final kaoIdx = _tick % _kaomoji.length;         // 每拍必然换脸
          final dots = 1 + (_tick % 3);                    // 1→2→3 个点循环
          final bob = (_tick % 2 == 0) ? -3.0 : 0.0;       // 上下跳
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Transform.translate(
                offset: Offset(0, bob),
                child: Text(_kaomoji[kaoIdx],
                    style: TextStyle(fontSize: 13, color: accent, height: 1)),
              ),
              const SizedBox(width: 4),
              SizedBox(
                width: 16,
                child: Text('.' * dots,
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: accent, height: 1)),
              ),
            ],
          );
        },
      ),
    );
  }
}
