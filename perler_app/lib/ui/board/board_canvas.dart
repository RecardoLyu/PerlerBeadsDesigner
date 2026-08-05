import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../algo/quantizer.dart';
import '../../state/app_state.dart';
import '../../theme/candy_theme.dart';

/// 图纸画板画布：实时 CustomPainter 绘制底板 + 网格 + 真实风豆子
/// （比例同 ChartPainter._drawBead），单指绘制、双指捏合缩放/平移。
/// 手势与交互逻辑对齐 canvas_area.dart 的瞬时手势模型。
class BoardCanvas extends ConsumerStatefulWidget {
  const BoardCanvas({super.key});

  @override
  ConsumerState<BoardCanvas> createState() => _BoardCanvasState();
}

class _BoardCanvasState extends ConsumerState<BoardCanvas> {
  final TransformationController _tx = TransformationController();
  // 双指缩放/平移起始快照
  Matrix4 _startMatrix = Matrix4.identity();
  Offset _startFocal = Offset.zero;
  bool _multiTouch = false;
  // 进行中的单指笔画（去重格集合），松手一次性提交
  final Set<int> _stroke = <int>{};
  // 框选起止（格坐标）
  (int, int)? _rectStart, _rectEnd;
  // 底图调整模式：拖拽/捏合起始快照（等比例变换，不改画布）
  double _startBaseScale = 1.0;
  double _startBaseOffX = 0.0, _startBaseOffY = 0.0;
  bool _wasAdjusting = false;

  @override
  void dispose() {
    _tx.dispose();
    super.dispose();
  }

  void _zoom(double factor) {
    final cur = _tx.value.clone();
    final scale = (cur.getMaxScaleOnAxis() * factor).clamp(0.2, 12.0);
    final center = context.size?.center(Offset.zero) ?? Offset.zero;
    final inv = Matrix4.inverted(cur);
    final focal = MatrixUtils.transformPoint(inv, center);
    _tx.value = cur.clone()
      ..translate(focal.dx, focal.dy)
      ..scale(scale / cur.getMaxScaleOnAxis())
      ..translate(-focal.dx, -focal.dy);
  }

  void _fit() => _tx.value = Matrix4.identity();

  /// 显示坐标 → 画板格坐标（画板是边长 = size 的正方形，铺满显示框）。
  (int, int)? _toCell(Offset local, Size box, int size) {
    final side = box.shortestSide;
    final offX = (box.width - side) / 2, offY = (box.height - side) / 2;
    final cell = side / size;
    final x = ((local.dx - offX) / cell).floor();
    final y = ((local.dy - offY) / cell).floor();
    if (x < 0 || y < 0 || x >= size || y >= size) return null;
    return (x, y);
  }

  void _onScaleStart(ScaleStartDetails d, Size box, BoardState b) {
    // 底图调整模式：单/双指都改派给底图（拖动/捏合），不绘制、不缩放画布
    if (b.baseAdjusting) {
      _startBaseScale = b.baseScale;
      _startBaseOffX = b.baseOffX;
      _startBaseOffY = b.baseOffY;
      _startFocal = d.focalPoint;
      return;
    }
    _multiTouch = d.pointerCount >= 2;
    if (_multiTouch) {
      _stroke.clear();
      _rectStart = _rectEnd = null;
      _startMatrix = _tx.value.clone();
      _startFocal = d.focalPoint;
      return;
    }
    final cell = _toCell(d.localFocalPoint, box, b.size);
    if (cell == null) return;
    final n = ref.read(boardProvider.notifier);
    switch (b.tool) {
      case BoardTool.fill:
        n.fill(cell.$1, cell.$2, b.color);
        break;
      case BoardTool.rect:
        setState(() { _rectStart = cell; _rectEnd = cell; });
        break;
      case BoardTool.pen:
      case BoardTool.eraser:
        _stroke.clear();
        _stroke.addAll(n.stampCells(cell.$1, cell.$2));
        setState(() {});
        break;
    }
  }

  void _onScaleUpdate(ScaleUpdateDetails d, Size box, BoardState b) {
    // 底图调整模式：双指捏合缩放底图、拖动平移底图（等比例，画布锁定）
    if (b.baseAdjusting) {
      final side = box.shortestSide;
      final cell = side / b.size;
      // 平移（单指或双指拖动）
      var offX = _startBaseOffX + (d.focalPoint.dx - _startFocal.dx) / cell;
      var offY = _startBaseOffY + (d.focalPoint.dy - _startFocal.dy) / cell;
      // 双指捏合缩放：以起始 focal 为锚，等比例
      var scale = _startBaseScale;
      if (d.pointerCount >= 2) {
        scale = (_startBaseScale * d.scale).clamp(0.02, 40.0);
        // focal-fixed：保持锚点下的图点不动。锚点格坐标 = (localFocal-off)/cell
        final offBx = (box.width - side) / 2, offBy = (box.height - side) / 2;
        final ax = (_startFocal.dx - offBx) / cell;   // 锚点（画板格坐标）
        final ay = (_startFocal.dy - offBy) / cell;
        final k = scale / _startBaseScale;
        offX = ax - (ax - _startBaseOffX) * k;
        offY = ay - (ay - _startBaseOffY) * k;
      }
      ref.read(boardProvider.notifier).setBaseTransform(scale, offX, offY);
      return;
    }
    if (d.pointerCount >= 2) _multiTouch = true;
    if (_multiTouch) {
      final scale = d.scale.clamp(0.2, 12.0);
      final m = _startMatrix.clone();
      final inv = Matrix4.inverted(_startMatrix);
      final anchor = MatrixUtils.transformPoint(inv, _startFocal);
      m.translate(anchor.dx, anchor.dy);
      m.scale(scale);
      m.translate(-anchor.dx, -anchor.dy);
      m.translate(d.focalPoint.dx - _startFocal.dx,
          d.focalPoint.dy - _startFocal.dy);
      _tx.value = m;
      return;
    }
    final cell = _toCell(d.localFocalPoint, box, b.size);
    if (cell == null) return;
    if (b.tool == BoardTool.rect && _rectStart != null) {
      setState(() => _rectEnd = cell);
      return;
    }
    if (b.tool == BoardTool.pen || b.tool == BoardTool.eraser) {
      _stroke.addAll(ref.read(boardProvider.notifier).stampCells(cell.$1, cell.$2));
      setState(() {});
    }
  }

  void _onScaleEnd(ScaleEndDetails d, BoardState b) {
    // 底图调整模式：不提交笔画，仅结束本次拖拽
    if (b.baseAdjusting) return;
    final n = ref.read(boardProvider.notifier);
    if (b.tool == BoardTool.rect && _rectStart != null && _rectEnd != null) {
      final x1 = _rectStart!.$1 < _rectEnd!.$1 ? _rectStart!.$1 : _rectEnd!.$1;
      final y1 = _rectStart!.$2 < _rectEnd!.$2 ? _rectStart!.$2 : _rectEnd!.$2;
      final x2 = _rectStart!.$1 > _rectEnd!.$1 ? _rectStart!.$1 : _rectEnd!.$1;
      final y2 = _rectStart!.$2 > _rectEnd!.$2 ? _rectStart!.$2 : _rectEnd!.$2;
      n.rectFill(x1, y1, x2, y2, b.color);
    } else if ((b.tool == BoardTool.pen || b.tool == BoardTool.eraser) &&
        _stroke.isNotEmpty && !_multiTouch) {
      n.stroke(_stroke, b.tool == BoardTool.eraser ? null : b.color);
    }
    _multiTouch = false;
    setState(() {
      _stroke.clear();
      _rectStart = _rectEnd = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final b = ref.watch(boardProvider);
    ref.watch(boardProvider.select((s) => s.version));

    if (!b.hasBoard) {
      return Center(
        child: Text('初始化画板…', style: TextStyle(fontSize: 13, color: c.mutedFg)),
      );
    }

    // 进入「调整底图」边沿：画布强制复位默认缩放并锁定（期间角落缩放按钮失效）
    if (b.baseAdjusting && !_wasAdjusting) _fit();
    _wasAdjusting = b.baseAdjusting;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: c.border),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [c.bg2, c.bg],
          ),
        ),
        child: Stack(
          children: [
            Positioned.fill(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: LayoutBuilder(builder: (context, constraints) {
                  final box = Size(constraints.maxWidth, constraints.maxHeight);
                  return InteractiveViewer(
                    transformationController: _tx,
                    minScale: 0.2,
                    maxScale: 12.0,
                    boundaryMargin: const EdgeInsets.all(double.infinity),
                    // 画板始终接管手势（单指绘制、双指缩放平移），关闭 InteractiveViewer 自带手势
                    panEnabled: false,
                    scaleEnabled: false,
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onScaleStart: (d) => _onScaleStart(d, box, b),
                      onScaleUpdate: (d) => _onScaleUpdate(d, box, b),
                      onScaleEnd: (d) => _onScaleEnd(d, b),
                      child: CustomPaint(
                        painter: _BoardPainter(
                          state: b,
                          stroke: _stroke,
                          rectStart: _rectStart,
                          rectEnd: _rectEnd,
                        ),
                        size: Size.infinite,
                      ),
                    ),
                  );
                }),
              ),
            ),
            // 画布上方：真实风/图纸风 切换入口（与电脑端画板态顶部切换对齐）
            Positioned(
              top: 12, left: 0, right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: c.surfaceStrong,
                    border: Border.all(color: c.border),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _StylePill(label: '真实风', selected: b.style == 'real',
                          onTap: () => ref.read(boardProvider.notifier).setStyle('real')),
                      _StylePill(label: '图纸风', selected: b.style == 'square',
                          onTap: () => ref.read(boardProvider.notifier).setStyle('square')),
                    ],
                  ),
                ),
              ),
            ),
            // 角落缩放工具（调整底图模式期间锁定）
            Positioned(
              left: 12, top: 0, bottom: 0,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _Mini(icon: Icons.zoom_in_rounded,
                      onTap: () { if (!b.baseAdjusting) _zoom(1.25); }),
                  const SizedBox(height: 8),
                  _Mini(icon: Icons.zoom_out_rounded,
                      onTap: () { if (!b.baseAdjusting) _zoom(0.8); }),
                  const SizedBox(height: 8),
                  _Mini(icon: Icons.fit_screen_rounded,
                      onTap: () { if (!b.baseAdjusting) _fit(); }),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 画布上方风格切换 pill（参照 canvas_area 顶部视图切换样式）。
class _StylePill extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _StylePill({required this.label, required this.selected, required this.onTap});
  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          gradient: selected ? candyPrimaryGradient(context) : null,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
                color: selected ? Colors.white : c.mutedFg)),
      ),
    );
  }
}

class _Mini extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _Mini({required this.icon, required this.onTap});
  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40, height: 40,
        decoration: BoxDecoration(
          color: c.surface,
          border: Border.all(color: c.border),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Icon(icon, size: 18, color: c.foreground),
      ),
    );
  }
}

/// 画板绘制层：底板 + 底图（高透明叠加）+ 网格 + 豆子 + 进行中笔画/框选预览。
class _BoardPainter extends CustomPainter {
  final BoardState state;
  final Set<int> stroke;
  final (int, int)? rectStart, rectEnd;
  const _BoardPainter({
    required this.state,
    required this.stroke,
    this.rectStart,
    this.rectEnd,
  });

  static const Color _pegboard = Color(0xFFF5F3EE);

  Color _hex(String hex) =>
      Color(0xFF000000 | int.parse(hex.substring(1), radix: 16));

  void _drawBead(Canvas canvas, double x1, double y1, double cell, Color rgb) {
    if (state.style != 'real') {
      canvas.drawRect(Rect.fromLTWH(x1, y1, cell, cell), Paint()..color = rgb);
      return;
    }
    final cx = x1 + cell / 2, cy = y1 + cell / 2;
    final r = cell * 0.46;
    Color scale(double f) => Color.fromARGB(255, (rgb.red * f).round(),
        (rgb.green * f).round(), (rgb.blue * f).round());
    canvas.drawCircle(Offset(cx, cy), r, Paint()..color = scale(0.72));
    canvas.drawCircle(Offset(cx, cy), r * 0.82, Paint()..color = rgb);
    final hr = cell * 0.13;
    canvas.drawCircle(Offset(cx, cy), hr, Paint()..color = scale(0.55));
    canvas.drawCircle(Offset(cx, cy), hr * 0.72, Paint()..color = _pegboard);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final s = state.size;
    final side = size.shortestSide;
    final offX = (size.width - side) / 2, offY = (size.height - side) / 2;
    final cell = side / s;
    final codeToColor = {for (final c in state.palette?.colors ?? <BeadColor>[]) c.code: c};
    Color colOf(String? code) {
      if (code == null) return _pegboard;
      final c = codeToColor[code];
      return c == null ? const Color(0xFF808080) : _hex(c.hex);
    }

    // 底板
    canvas.drawRect(
        Rect.fromLTWH(offX, offY, side, side), Paint()..color = _pegboard);

    // 底图（等比例缩放+偏移叠加，画板内裁切；只改底图不动画板）
    if (state.baseImage != null && state.baseVisible) {
      final img = state.baseImage!;
      final src = Rect.fromLTWH(0, 0, img.width.toDouble(), img.height.toDouble());
      final w = state.baseW * state.baseScale * cell;
      final h = state.baseH * state.baseScale * cell;
      final dx = offX + state.baseOffX * cell, dy = offY + state.baseOffY * cell;
      final dst = Rect.fromLTWH(dx, dy, w, h);
      canvas.save();
      canvas.clipRect(Rect.fromLTWH(offX, offY, side, side));   // 只画板内
      canvas.drawImageRect(
          img, src, dst,
          Paint()
            ..color = Colors.white.withOpacity(state.baseOpacity)
            ..filterQuality = FilterQuality.medium);
      canvas.restore();
    }

    // 网格线
    final gridPaint = Paint()
      ..color = const Color(0x14000000)
      ..strokeWidth = 1;
    for (var i = 0; i <= s; i++) {
      final p = offX + i * cell;
      canvas.drawLine(Offset(p, offY), Offset(p, offY + side), gridPaint);
      final q = offY + i * cell;
      canvas.drawLine(Offset(offX, q), Offset(offX + side, q), gridPaint);
    }

    // 已提交的豆
    for (var y = 0; y < s; y++) {
      for (var x = 0; x < s; x++) {
        final code = state.grid[y * s + x];
        if (code != null) {
          _drawBead(canvas, offX + x * cell, offY + y * cell, cell, colOf(code));
        }
      }
    }

    // 进行中笔画（未提交）
    for (final i in stroke) {
      final x = i % s, y = i ~/ s;
      final code = state.tool == BoardTool.eraser ? null : state.color;
      if (code != null) {
        _drawBead(canvas, offX + x * cell, offY + y * cell, cell, colOf(code));
      } else {
        canvas.drawRect(
            Rect.fromLTWH(offX + x * cell, offY + y * cell, cell, cell),
            Paint()..color = _pegboard);
      }
    }

    // 框选预览
    if (rectStart != null && rectEnd != null) {
      final x1 = rectStart!.$1 < rectEnd!.$1 ? rectStart!.$1 : rectEnd!.$1;
      final y1 = rectStart!.$2 < rectEnd!.$2 ? rectStart!.$2 : rectEnd!.$2;
      final x2 = rectStart!.$1 > rectEnd!.$1 ? rectStart!.$1 : rectEnd!.$1;
      final y2 = rectStart!.$2 > rectEnd!.$2 ? rectStart!.$2 : rectEnd!.$2;
      final rect = Rect.fromLTWH(
          offX + x1 * cell, offY + y1 * cell,
          (x2 - x1 + 1) * cell, (y2 - y1 + 1) * cell);
      canvas.drawRect(
          rect,
          Paint()
            ..color = const Color(0xFF7C3AED).withOpacity(0.12));
      canvas.drawRect(
          rect,
          Paint()
            ..color = const Color(0xFF7C3AED)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2);
    }
  }

  @override
  bool shouldRepaint(_BoardPainter old) => true;
}
