import 'dart:async';
import 'dart:math';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/candy_theme.dart';
import '../../state/app_state.dart';
import '../../state/skin_state.dart';
import 'canvas/canvas_area.dart';
import 'board/board_canvas.dart';
import 'sheet/function_sheet.dart';
import 'settings/settings_screen.dart';

/// 主界面：顶部精简栏 + 画布（上）+ Bottom Sheet 功能栏（下）
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.candy;
    ref.watch(themeModeProvider); // 主题切换时重建顶栏图标
    final skinOn = ref.watch(skinProvider).enabled; // 换肤时隐藏硬编码色 blob
    final tab = ref.watch(sheetTabProvider); // 当前底部 Tab：board 时主预览区切画板画布

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
              // 漂浮 blob 背景（换肤开启时由壁纸替代）
              if (!skinOn) ...[
                const _Blob(top: -120, left: -120, size: 420, color: Color(0xFFFB7185)),
                const _Blob(bottom: -140, right: -100, size: 380, color: Color(0xFFA78BFA)),
              ],

              Column(
                children: [
                  _TopBar(
                    isDark: Theme.of(context).brightness == Brightness.dark,
                    onToggleTheme: () => ref.read(themeModeProvider.notifier).toggle(),
                  ),
                  const _StatusLine(),
                  // 主预览区：图像转换/图纸生成=图像画布，图纸画板=画板画布
                  Expanded(child: tab == SheetTab.board ? const BoardCanvas() : const CanvasArea()),
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
          const Spacer(),
          _IconBtn(icon: isDark ? Icons.dark_mode_rounded : Icons.light_mode_rounded, onTap: onToggleTheme, tooltip: '切换主题'),
          const SizedBox(width: 9),
          _IconBtn(
            icon: Icons.settings_rounded,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
            tooltip: '设置',
          ),
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
    final busy = ref.watch(busyProvider);
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 8),
      child: Row(
        children: [
          // 状态点：忙碌=红、空闲=绿（计算占满主 isolate 时颜文字会卡，
          // 这个色点是立即可见的忙碌反馈）
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: 7, height: 7,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: busy ? const Color(0xFFEF4444) : const Color(0xFF16A34A),
            ),
          ),
          const SizedBox(width: 8),
          // 颜文字常显（忙碌时轮换跳动，空闲时静态显示），文案在右
          const _BusyIndicator(),
          Expanded(child: Text(msg, style: TextStyle(fontSize: 11.5, color: c.mutedFg), overflow: TextOverflow.ellipsis)),
        ],
      ),
    );
  }
}

/// 状态行颜文字：桌面版同款（忙碌时 600ms 轮换 + 上下浮动 + 跳动省略号）。
/// 常显：忙碌时轮换跳动并带省略号，空闲时静态显示一只，让状态行始终有这个标志性表情。
class _BusyIndicator extends ConsumerStatefulWidget {
  const _BusyIndicator();
  @override
  ConsumerState<_BusyIndicator> createState() => _BusyIndicatorState();
}

class _BusyIndicatorState extends ConsumerState<_BusyIndicator>
    with SingleTickerProviderStateMixin {
  // 桌面版颜文字集合（src/webapp/static/js/shell.js KAOMOJI.busy / idle）
  static const _kaomojiBusy = [
    '(◕‿◕)', '(｡♥‿♥｡)', '(≧◡≦)', '(ﾉ◕ヮ◕)ﾉ', '(◠‿◠)',
    '(✿◠‿◠)', '(¬‿¬)', '(☆▽☆)', '(ღ˘⌣˘ღ)', '(∩^o^)⊃',
  ];
  static const _kaomojiIdle = '(´・ω・`)';

  // 换脸节奏：500ms 一个（用户反馈原先 600ms 连带每拍跳动显得闪得太快）。
  static const _faceMs = 500;
  // 省略号 1→2→3 循环：放慢到 1000ms，避免跟换脸叠出急促感。
  static const _dotsMs = 1000;

  late final AnimationController _ctl; // 连续 bob 浮动（不驱动换脸）
  int _faceIdx = 0;
  int _dotCount = 1;
  Timer? _faceTimer;
  Timer? _dotsTimer;

  @override
  void initState() {
    super.initState();
    // bob：1.6s 一个往返的缓动正弦浮动（轻微上下），只看不做换脸。
    _ctl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1600))
      ..repeat();
    // 换脸：固定 500ms 切到下一张
    _faceTimer =
        Timer.periodic(const Duration(milliseconds: _faceMs), (_) {
      if (mounted) setState(() => _faceIdx = (_faceIdx + 1) % _kaomojiBusy.length);
    });
    // 省略号：固定 1000ms 增一个点（1→2→3 循环）
    _dotsTimer =
        Timer.periodic(const Duration(milliseconds: _dotsMs), (_) {
      if (mounted) setState(() => _dotCount = 1 + (_dotCount % 3));
    });
  }

  @override
  void dispose() {
    _ctl.dispose();
    _faceTimer?.cancel();
    _dotsTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(busyProvider);
    final accent = Theme.of(context).colorScheme.primary;
    return Padding(
      padding: const EdgeInsets.only(right: 7),
      child: AnimatedBuilder(
        animation: _ctl,
        builder: (_, __) {
          if (!busy) {
            // 空闲：静态颜文字，不跳动、无省略号
            return Text(_kaomojiIdle,
                style: TextStyle(fontSize: 13, color: accent, height: 1));
          }
          // bob：正弦缓动上下浮动（-2~+2 像素，轻微，不刺眼）
          final bob = 2.0 * sin(2 * pi * _ctl.value);
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Transform.translate(
                offset: Offset(0, bob),
                // 换脸加一点微动效：轻微淡入 + 放大到位，过渡不生硬
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 220),
                  transitionBuilder: (child, anim) => FadeTransition(
                    opacity: anim,
                    child: ScaleTransition(
                        scale: Tween(begin: 0.85, end: 1.0).animate(anim),
                        child: child),
                  ),
                  child: Text(_kaomojiBusy[_faceIdx],
                      key: ValueKey(_faceIdx),
                      style: TextStyle(fontSize: 13, color: accent, height: 1)),
                ),
              ),
              const SizedBox(width: 4),
              SizedBox(
                width: 16,
                child: Text('.' * _dotCount,
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        color: accent,
                        height: 1)),
              ),
            ],
          );
        },
      ),
    );
  }
}
