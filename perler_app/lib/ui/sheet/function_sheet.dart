import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/candy_theme.dart';
import '../../state/app_state.dart';
import '../panels/image_adjust_panel.dart';
import '../panels/pattern_gen_panel.dart';
import '../panels/board_panel.dart';

/// 底部功能 Tab：图像调整 / 图纸生成 / 图纸画板（整合自原 调整+分割 / 图纸+导出）
enum SheetTab { adjust, pattern, board }

/// Sheet 开合请求：递增计数即请求「收起到 collapsed」。
/// 各面板操作完成后（如应用调整）触发，让用户立刻看到画布效果。
final sheetCollapseRequestProvider = StateProvider<int>((_) => 0);

/// 当前底部 Tab（提升到 provider，主预览区据此切换 图像画布 / 图纸画板画布）。
final sheetTabProvider = StateProvider<SheetTab>((_) => SheetTab.adjust);

class FunctionSheet extends ConsumerStatefulWidget {
  const FunctionSheet({super.key});

  @override
  ConsumerState<FunctionSheet> createState() => _FunctionSheetState();
}

class _FunctionSheetState extends ConsumerState<FunctionSheet> {
  SheetTab _tab = SheetTab.adjust;
  final DraggableScrollableController _ctrl = DraggableScrollableController();

  // 三档：收起 / 半开（默认）/ 全开
  static const double _collapsed = 0.13;
  static const double _half = 0.46;
  static const double _full = 0.82;

  void _onTabTap(SheetTab t) {
    final same = _tab == t;
    // 切到不同面板：取消进行中的画布子交互（框选/涂抹/裁剪），防止泄露。
    if (!same) cancelCanvasInteraction(ref);
    setState(() => _tab = t);
    // 同步到 provider，主预览区据此切换 图像画布 / 图纸画板画布
    ref.read(sheetTabProvider.notifier).state = t;
    // 进入画板时确保已建板
    if (t == SheetTab.board) {
      Future.microtask(() => ref.read(boardProvider.notifier).ensure());
    }
    // 点当前已选 Tab：在半开/收起间切换；点其它：升到半开。
    // 注意：用 easeOutCubic 而非 easeOutBack —— easeOutBack 过冲会让 _ctrl.size
    // 瞬时越出 [min,max] 区间，DraggableScrollableSheet 尺寸异常 → 巨大/负高度
    // → RenderFlex 「BOTTOM OVERFLOWED BY 99696 PIXELS」断言（红黄闪烁的根源）。
    if (same) {
      final cur = _ctrl.size;
      final target = (cur - _half).abs() < 0.02 ? _collapsed : _half;
      _ctrl.animateTo(target,
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic);
    } else {
      _ctrl.animateTo(_half,
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic);
    }
  }

  // 顶部把手区（grabber + TabBar）整体可垂直拖动 → 驱动 sheet 开合。
  // DraggableScrollableSheet 默认只在内容滚动区响应拖动，故这里手动接手势。
  void _onDragUpdate(DragUpdateDetails d) {
    final screenH = MediaQuery.of(context).size.height;
    final next = (_ctrl.size - d.primaryDelta! / screenH).clamp(_collapsed, _full);
    _ctrl.jumpTo(next);
  }

  void _onDragEnd(DragEndDetails d) {
    // 松手吸附到最近档位
    final sizes = [_collapsed, _half, _full];
    final cur = _ctrl.size;
    final v = d.primaryVelocity ?? 0;
    double target;
    if (v < -300) {
      target = sizes.lastWhere((s) => s > cur, orElse: () => _full); // 上甩
    } else if (v > 300) {
      target = sizes.firstWhere((s) => s < cur, orElse: () => _collapsed); // 下甩
    } else {
      target = sizes.reduce((a, b) => (a - cur).abs() < (b - cur).abs() ? a : b);
    }
    _ctrl.animateTo(target, duration: const Duration(milliseconds: 220), curve: Curves.easeOutCubic);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    // 监听「请求收起」信号（面板操作完成后触发）→ 收起 sheet 露出画布
    ref.listen(sheetCollapseRequestProvider, (prev, next) {
      if (next != prev) {
        _ctrl.animateTo(_collapsed,
            duration: const Duration(milliseconds: 300), curve: Curves.easeOutCubic);
      }
    });
    return DraggableScrollableSheet(
      controller: _ctrl,
      initialChildSize: _half,
      minChildSize: _collapsed,
      maxChildSize: _full,
      snap: true,
      snapSizes: const [_collapsed, _half, _full],
      builder: (context, scroll) {
        final dark = Theme.of(context).brightness == Brightness.dark;
        return ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: kGlassBlur, sigmaY: kGlassBlur),
            child: Container(
              decoration: BoxDecoration(
                // 暗色下用更实的底色：浅色图像透过玻璃模糊后仍可能偏亮，
                // 加浓不透明度保证叠在上面的文字/图标可读。
                color: dark ? c.surfaceStrong : c.surface,
                border: Border(top: BorderSide(color: c.border)),
              ),
              child: Column(
                children: [
                  // 把手区可拖（grabber + TabBar 都包进手势）
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onVerticalDragUpdate: _onDragUpdate,
                    onVerticalDragEnd: _onDragEnd,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const _Grabber(),
                        _TabBar(current: _tab, onTap: _onTabTap),
                      ],
                    ),
                  ),
                  const SizedBox(height: 2),
                  Expanded(
                    child: SingleChildScrollView(
                      controller: scroll,
                      padding: const EdgeInsets.fromLTRB(16, 2, 16, 20),
                      child: _panelFor(_tab),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _panelFor(SheetTab t) {
    switch (t) {
      case SheetTab.adjust:
        return const ImageAdjustPanel();   // 调整 + 分割
      case SheetTab.pattern:
        return const PatternGenPanel();    // 图纸 + 导出
      case SheetTab.board:
        return const BoardPanel();         // 图纸画板
    }
  }
}

class _Grabber extends StatelessWidget {
  const _Grabber();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 2),
      child: Container(
        width: 44,
        height: 5,
        decoration: BoxDecoration(
          color: context.candy.mutedFg.withOpacity(0.5),
          borderRadius: BorderRadius.circular(999),
        ),
      ),
    );
  }
}

class _TabBar extends StatelessWidget {
  final SheetTab current;
  final ValueChanged<SheetTab> onTap;
  const _TabBar({required this.current, required this.onTap});

  static const _items = [
    (SheetTab.adjust, Icons.tune_rounded, '图像调整'),
    (SheetTab.pattern, Icons.grid_on_rounded, '图纸生成'),
    (SheetTab.board, Icons.brush_rounded, '图纸画板'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 6, 10, 10),
      child: Row(
        children: _items.map((it) {
          final on = it.$1 == current;
          return Expanded(
            child: GestureDetector(
              onTap: () => onTap(it.$1),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOutCubic,
                margin: const EdgeInsets.symmetric(horizontal: 3),
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: BoxDecoration(
                  gradient: on ? candyPrimaryGradient(context) : null,
                  borderRadius: BorderRadius.circular(15),
                  // 阴影始终给非空列表：AnimatedContainer 在 null↔list 间隐式插值时，
                  // 中间帧会产生非法 blurRadius（NaN/负）触发 dart:ui 断言 → 红黄错误闪烁。
                  // 未选中态用「零模糊全透明」阴影占位，插值全程合法。
                  boxShadow: [
                    BoxShadow(
                      color: on ? c.violetDeep.withOpacity(0.35) : Colors.transparent,
                      blurRadius: on ? 14 : 0,
                      offset: on ? const Offset(0, 4) : Offset.zero,
                    )
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(it.$2, size: 20, color: on ? Colors.white : c.mutedFg),
                    const SizedBox(height: 4),
                    Text(
                      it.$3,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: on ? Colors.white : c.mutedFg,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
