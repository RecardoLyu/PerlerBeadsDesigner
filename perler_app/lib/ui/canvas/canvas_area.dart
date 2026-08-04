import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../theme/candy_theme.dart';
import '../../state/app_state.dart';

/// 画布区：加载后显示真实图像（InteractiveViewer 缩放/平移）+ 视图四模式
/// 切换 + 角落缩放工具 + 鹰眼 minimap。M2 在这里加涂抹/框选叠层。
class CanvasArea extends ConsumerStatefulWidget {
  const CanvasArea({super.key});

  @override
  ConsumerState<CanvasArea> createState() => _CanvasAreaState();
}

class _CanvasAreaState extends ConsumerState<CanvasArea> {
  static const _modes = [
    (CanvasViewMode.original, '原图'),
    (CanvasViewMode.highlight, '高亮'),
    (CanvasViewMode.mask, 'Mask'),
    (CanvasViewMode.applied, '应用结果'),
    (CanvasViewMode.pattern, '图纸'),
  ];

  final TransformationController _tx = TransformationController();

  @override
  void dispose() {
    _tx.dispose();
    super.dispose();
  }

  void _zoom(double factor) {
    final cur = _tx.value.clone();
    final scale = (cur.getMaxScaleOnAxis() * factor).clamp(0.2, 12.0);
    // 以画布中心为锚点缩放
    final center = context.size?.center(Offset.zero) ?? Offset.zero;
    final inv = Matrix4.inverted(cur);
    final focal = MatrixUtils.transformPoint(inv, center);
    _tx.value = cur.clone()
      ..translate(focal.dx, focal.dy)
      ..scale(scale / cur.getMaxScaleOnAxis())
      ..translate(-focal.dx, -focal.dy);
  }

  void _fit() => _tx.value = Matrix4.identity();

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final mode = ref.watch(viewModeProvider);
    final imgState = ref.watch(imageProvider);
    final working = imgState.working;
    final segBusy = ref.watch(segmentProvider).busy;
    final patBusy = ref.watch(patternProvider).busy;

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
            // 径向渐变氛围（用主题 violet：换肤后随皮肤色跟随）
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(24),
                  gradient: RadialGradient(
                    center: const Alignment(-0.5, -0.4),
                    radius: 1.2,
                    colors: [c.violet.withOpacity(0.18), Colors.transparent],
                  ),
                ),
              ),
            ),

            // 图像层（有图）或 空态（无图）
            if (working != null)
              Positioned.fill(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: _CanvasContent(working: working, tx: _tx),
                ),
              )
            else
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.image_outlined, size: 52, color: c.mutedFg.withOpacity(0.5)),
                    const SizedBox(height: 8),
                    Text('尚未加载图像', style: TextStyle(fontSize: 13.5, color: c.mutedFg)),
                    const SizedBox(height: 4),
                    Text('在「调整」页点「加载图像」',
                        style: TextStyle(fontSize: 11, color: c.mutedFg.withOpacity(0.7))),
                  ],
                ),
              ),

            // 处理中遮罩（图像处理 / 分割 / 图纸生成 任一忙碌即显示）
            if (imgState.busy || segBusy || patBusy)
              Positioned.fill(
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    color: c.bg.withOpacity(0.45),
                  ),
                  child: const Center(child: CircularProgressIndicator()),
                ),
              ),

            // 顶部视图四模式切换
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
                    children: _modes.map((m) {
                      final on = m.$1 == mode;
                      return GestureDetector(
                        onTap: () => ref.read(viewModeProvider.notifier).state = m.$1,
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            gradient: on ? candyPrimaryGradient(context) : null,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(m.$2,
                              style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: on ? Colors.white : c.mutedFg)),
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
            ),

            // 角落缩放工具（左中）——有图才可用
            Positioned(
              left: 12, top: 0, bottom: 0,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _MiniTool(
                      icon: Icons.zoom_in_rounded,
                      tooltip: '放大',
                      onTap: working != null ? () => _zoom(1.25) : null),
                  const SizedBox(height: 8),
                  _MiniTool(
                      icon: Icons.zoom_out_rounded,
                      tooltip: '缩小',
                      onTap: working != null ? () => _zoom(0.8) : null),
                  const SizedBox(height: 8),
                  _MiniTool(
                      icon: Icons.fit_screen_rounded,
                      tooltip: '适应窗口',
                      onTap: working != null ? _fit : null),
                ],
              ),
            ),

            // 鹰眼 minimap（有图时显示缩略图，无图时占位）
            Positioned(
              right: 12, bottom: 12,
              child: Container(
                width: 104, height: 74,
                padding: const EdgeInsets.all(5),
                decoration: BoxDecoration(
                  color: c.surfaceStrong,
                  border: Border.all(color: c.border),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: working != null
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(9),
                        child: RawImage(image: working.uiImage, fit: BoxFit.cover),
                      )
                    : Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(9),
                          gradient: const LinearGradient(
                            begin: Alignment.topLeft, end: Alignment.bottomRight,
                            colors: [Color(0xFFFBD5DE), Color(0xFFC4B5FD)],
                          ),
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniTool extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onTap;
  const _MiniTool({required this.icon, required this.tooltip, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final enabled = onTap != null;
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Opacity(
          opacity: enabled ? 1.0 : 0.45,
          child: Container(
            width: 40, height: 40,
            decoration: BoxDecoration(color: c.surface, border: Border.all(color: c.border), borderRadius: BorderRadius.circular(14)),
            child: Icon(icon, size: 18, color: c.foreground),
          ),
        ),
      ),
    );
  }
}

/// 图像显示。视图模式为 original 时显示原图；
/// 否则显示状态层已合成好的小图（分割完成时离线合成一次，零逐像素计算）。
/// 这是性能关键：画布只显示一张缓存 ui.Image，绝不逐像素画掩码。
class _ImageWithMask extends ConsumerStatefulWidget {
  final WorkingImage working;
  final CanvasViewMode mode;
  const _ImageWithMask({required this.working, required this.mode});

  @override
  ConsumerState<_ImageWithMask> createState() => _ImageWithMaskState();
}

class _ImageWithMaskState extends ConsumerState<_ImageWithMask> {
  @override
  void initState() {
    super.initState();
    // 视图模式变化时让状态层重建合成图
    ref.listenManual(viewModeProvider, (_, __) {
      ref.read(segmentProvider.notifier).refreshComposite();
    });
  }

  @override
  Widget build(BuildContext context) {
    final seg = ref.watch(segmentProvider);
    // 显式 watch compositeVersion：composite 是 ui.Image，单靠引用比较
    // StateNotifier 不一定触发重建，版本号变化必定触发。
    ref.watch(segmentProvider.select((s) => s.compositeVersion));
    final composite = seg.composite;

    // 图纸模式：显示 ChartPainter 离线渲染好的完整图纸（锐利豆块 + 网格 + BOM 条）。
    if (widget.mode == CanvasViewMode.pattern) {
      ref.watch(patternProvider.select((s) => s.version));
      final chart = ref.watch(patternProvider).chartImage;
      if (chart != null) {
        // filterQuality.none：图纸已是锐利方块，不能再被采样糊掉
        return RawImage(
          image: chart,
          filterQuality: FilterQuality.none,
          fit: BoxFit.contain,
        );
      }
      // 无图纸：回落原图
      return RawImage(
        image: widget.working.uiImage,
        filterQuality: FilterQuality.medium,
        fit: BoxFit.contain,
      );
    }

    final useComposite = widget.mode != CanvasViewMode.original &&
        seg.hasMask &&
        composite != null;

    return RawImage(
      image: useComposite ? composite : widget.working.uiImage,
      filterQuality: FilterQuality.medium,
      fit: BoxFit.contain,
    );
  }
}

/// 画布内容：InteractiveViewer（缩放平移）+ 可选的框选/涂抹手势层。
/// 当 interaction == pan 时手势层关闭，InteractiveViewer 接收全部手势；
/// 否则手势层接管，把触摸点换算成图像像素坐标并喂给 SegmentNotifier。
class _CanvasContent extends ConsumerStatefulWidget {
  final WorkingImage working;
  final TransformationController tx;
  const _CanvasContent({required this.working, required this.tx});

  @override
  ConsumerState<_CanvasContent> createState() => _CanvasContentState();
}

class _CanvasContentState extends ConsumerState<_CanvasContent> {
  // 当前手势收集的图像像素坐标点
  final List<(double, double)> _pts = [];
  // 框选轨迹（显示坐标，用于实时画框选范围）
  final List<Offset> _selectDisplay = [];
  // 双指缩放/平移的起始快照（focal 固定缩放）
  Matrix4 _startMatrix = Matrix4.identity();
  Offset _startFocal = Offset.zero;
  // 双指手势进行中：单指涂抹/框选已开始后又加了第二指时，取消单指手势避免误涂/误框
  bool _multiTouch = false;

  // ---- 裁剪模式：可拖动的裁剪框（8 手柄 + 整体移动 + 新建）----
  String? _cropDrag; // 'tl/tr/bl/br/l/r/t/b/move/new'；null=未在拖
  Rect? _cropBox0; // 拖拽起始时的框（图像像素）
  (double, double)? _cropStart; // 拖拽起点（图像像素）
  static const double _cropHitPx = 26; // 手柄命中半径（显示像素，触屏放大）
  static const double _cropMinPx = 8; // 最小裁剪边长（图像像素）

  /// 图像在 child 坐标系里的实际显示矩形（BoxFit.contain）。
  Rect _imageRect(Size box) {
    final iw = widget.working.width.toDouble();
    final ih = widget.working.height.toDouble();
    final scale = (box.width / iw) < (box.height / ih) ? box.width / iw : box.height / ih;
    final dispW = iw * scale, dispH = ih * scale;
    final offX = (box.width - dispW) / 2, offY = (box.height - dispH) / 2;
    return Rect.fromLTWH(offX, offY, dispW, dispH);
  }

  /// 显示坐标 → 图像像素坐标（clamp 到图像内；越界的手指点映射到最近的边缘，
  /// 这样手指拖出图片边界时，框选的对边仍能贴着边界跟随）。
  (double, double) _toImageClamped(Offset local, Rect imgRect) {
    final iw = widget.working.width.toDouble();
    final ih = widget.working.height.toDouble();
    final cx = local.dx.clamp(imgRect.left, imgRect.right - 0.001);
    final cy = local.dy.clamp(imgRect.top, imgRect.bottom - 0.001);
    final x = ((cx - imgRect.left) / imgRect.width * iw).clamp(0.0, iw - 1);
    final y = ((cy - imgRect.top) / imgRect.height * ih).clamp(0.0, ih - 1);
    return (x, y);
  }

  /// 把显示坐标 clamp 到图像显示矩形内（可视化用，不画出界）。
  Offset _clampToRect(Offset p, Rect r) =>
      Offset(p.dx.clamp(r.left, r.right), p.dy.clamp(r.top, r.bottom));

  // ---- 裁剪框：图像像素 Rect ↔ 显示坐标 Rect 换算 ----
  Rect _cropToDisplay(Rect imgPx, Rect imgRect) {
    final iw = widget.working.width.toDouble(), ih = widget.working.height.toDouble();
    final l = imgRect.left + imgPx.left / iw * imgRect.width;
    final t = imgRect.top + imgPx.top / ih * imgRect.height;
    final r = imgRect.left + imgPx.right / iw * imgRect.width;
    final b = imgRect.top + imgPx.bottom / ih * imgRect.height;
    return Rect.fromLTRB(l, t, r, b);
  }

  /// 命中检测（显示坐标）：返回 'tl/tr/bl/br/l/r/t/b/move/new'。
  String _cropHit(Offset local, Rect box, Rect imgRect) {
    final d = _cropToDisplay(box, imgRect);
    double dx(Offset a, Offset b) => (a - b).distance;
    final corners = {
      'tl': d.topLeft, 'tr': d.topRight, 'bl': d.bottomLeft, 'br': d.bottomRight,
    };
    for (final e in corners.entries) {
      if (dx(local, e.value) <= _cropHitPx) return e.key;
    }
    final edges = {
      't': Offset(d.center.dx, d.top), 'b': Offset(d.center.dx, d.bottom),
      'l': Offset(d.left, d.center.dy), 'r': Offset(d.right, d.center.dy),
    };
    for (final e in edges.entries) {
      if (dx(local, e.value) <= _cropHitPx) return e.key;
    }
    // 框线附近吸附：点在某条边附近也算拖该边（触屏容错）
    final inX = local.dx >= d.left - _cropHitPx && local.dx <= d.right + _cropHitPx;
    final inY = local.dy >= d.top - _cropHitPx && local.dy <= d.bottom + _cropHitPx;
    if (inX && (local.dy - d.top).abs() <= _cropHitPx) return 't';
    if (inX && (local.dy - d.bottom).abs() <= _cropHitPx) return 'b';
    if (inY && (local.dx - d.left).abs() <= _cropHitPx) return 'l';
    if (inY && (local.dx - d.right).abs() <= _cropHitPx) return 'r';
    return d.contains(local) ? 'move' : 'new';
  }

  void _cropBegin(Offset local, Rect imgRect) {
    final cur = ref.read(cropRectProvider);
    final p = _toImageClamped(local, imgRect);
    if (cur == null) {
      // 尚无框：首次拖拽新建框
      _cropStart = p;
      _cropDrag = 'new';
      ref.read(cropRectProvider.notifier).state = Rect.fromPoints(Offset(p.$1, p.$2), Offset(p.$1, p.$2));
      _cropBox0 = null;
      return;
    }
    final kind = _cropHit(local, cur, imgRect);
    // 已有框：点框外不再重新框选，只能拖手柄/拖框内调整（带吸附容错）
    if (kind == 'new') return;
    _cropStart = p;
    _cropDrag = kind;
    _cropBox0 = cur;
  }

  void _cropUpdate(Offset local, Rect imgRect) {
    if (_cropDrag == null || _cropStart == null) return;
    final p = _toImageClamped(local, imgRect);
    final iw = widget.working.width.toDouble(), ih = widget.working.height.toDouble();
    double cx(double v) => v.clamp(0.0, iw);
    double cy(double v) => v.clamp(0.0, ih);
    if (_cropDrag == 'new') {
      final s = _cropStart!;
      ref.read(cropRectProvider.notifier).state =
          Rect.fromPoints(Offset(s.$1, s.$2), Offset(p.$1, p.$2));
      return;
    }
    final b = _cropBox0!;
    final dx = p.$1 - _cropStart!.$1, dy = p.$2 - _cropStart!.$2;
    final k = _cropDrag!;
    Rect nb;
    if (k == 'move') {
      final w = b.width, h = b.height;
      final nl = (b.left + dx).clamp(0.0, iw - w);
      final nt = (b.top + dy).clamp(0.0, ih - h);
      nb = Rect.fromLTWH(nl, nt, w, h);
    } else {
      double l = b.left, t = b.top, r = b.right, bo = b.bottom;
      if (k.contains('l')) l = cx(b.left + dx);
      if (k.contains('r')) r = cx(b.right + dx);
      if (k.contains('t')) t = cy(b.top + dy);
      if (k.contains('b')) bo = cy(b.bottom + dy);
      nb = Rect.fromLTRB(l, t, r, bo);
    }
    ref.read(cropRectProvider.notifier).state = nb;
  }

  void _cropEnd() {
    final cur = ref.read(cropRectProvider);
    if (cur != null) {
      final n = _normalizeRect(cur);
      // 过滤过小框
      if (n.width < _cropMinPx || n.height < _cropMinPx) {
        ref.read(cropRectProvider.notifier).state = null;
      } else {
        ref.read(cropRectProvider.notifier).state = n;
      }
    }
    _cropDrag = null; _cropBox0 = null; _cropStart = null;
  }

  static Rect _normalizeRect(Rect r) => Rect.fromLTRB(
        r.left < r.right ? r.left : r.right,
        r.top < r.bottom ? r.top : r.bottom,
        r.left < r.right ? r.right : r.left,
        r.top < r.bottom ? r.bottom : r.top,
      );

  /// 涂抹一笔（单指）。
  void _scribblePoint(Offset local, Size box, CanvasInteraction mode) {
    final imgRect = _imageRect(box);
    final p = _toImageClamped(local, imgRect);
    ref.read(segmentProvider.notifier)
        .scribbleAt(p.$1, p.$2, fg: mode == CanvasInteraction.scribbleFg);
  }

  // ---- 瞬时手势：单指=涂抹/框选，双指=平移+捏合缩放 ----
  // scale 手势单指时 scale==1.0 且 focalPoint 跟随手指 → 当作拖拽；
  // 双指时 scale 变化 → 手动做 focal 固定缩放/平移（InteractiveViewer 此时禁用自带手势）。

  void _onScaleStart(ScaleStartDetails d, Size box, CanvasInteraction mode) {
    _multiTouch = d.pointerCount >= 2;
    if (_multiTouch) {
      // 双指：取消可能已开始/即将开始的单指手势，进入缩放平移
      _pts.clear();
      _selectDisplay.clear();
      _cropDrag = null; _cropBox0 = null; _cropStart = null;
      _startMatrix = widget.tx.value.clone();
      _startFocal = d.focalPoint;
    } else {
      // 单指：涂抹/框选/裁剪起点
      final imgRect = _imageRect(box);
      if (mode == CanvasInteraction.crop) {
        _cropBegin(d.localFocalPoint, imgRect);
        return;
      }
      final p = _toImageClamped(d.localFocalPoint, imgRect);
      _pts.clear();
      _pts.add(p);
      _selectDisplay.clear();
      _selectDisplay.add(_clampToRect(d.localFocalPoint, imgRect));
      if (mode == CanvasInteraction.scribbleFg || mode == CanvasInteraction.scribbleBg) {
        _scribblePoint(d.localFocalPoint, box, mode);
      }
    }
  }

  void _onScaleUpdate(ScaleUpdateDetails d, Size box, CanvasInteraction mode) {
    if (d.pointerCount >= 2) _multiTouch = true;
    if (_multiTouch) {
      // 双指平移 + 捏合缩放：以起始 focal 为锚点
      final scale = d.scale.clamp(0.2, 12.0);
      final m = _startMatrix.clone();
      final inv = Matrix4.inverted(_startMatrix);
      final anchor = MatrixUtils.transformPoint(inv, _startFocal);
      m.translate(anchor.dx, anchor.dy);
      m.scale(scale);
      m.translate(-anchor.dx, -anchor.dy);
      m.translate(d.focalPoint.dx - _startFocal.dx, d.focalPoint.dy - _startFocal.dy);
      widget.tx.value = m;
      return;
    }
    // 单指拖拽：涂抹/框选/裁剪轨迹
    final imgRect = _imageRect(box);
    if (mode == CanvasInteraction.crop) {
      _cropUpdate(d.localFocalPoint, imgRect);
      return;
    }
    final p = _toImageClamped(d.localFocalPoint, imgRect);
    if (mode == CanvasInteraction.scribbleFg || mode == CanvasInteraction.scribbleBg) {
      _scribblePoint(d.localFocalPoint, box, mode);
    } else {
      _pts.add(p);
      setState(() {
        _selectDisplay.add(_clampToRect(d.localFocalPoint, imgRect));
      });
    }
  }

  void _onScaleEnd(ScaleEndDetails d, CanvasInteraction mode) {
    if (mode == CanvasInteraction.crop) {
      _cropEnd();
      setState(() {});
      return;
    }
    if (!_multiTouch &&
        (mode == CanvasInteraction.selectRect ||
            mode == CanvasInteraction.selectEllipse ||
            mode == CanvasInteraction.selectFree) &&
        _pts.isNotEmpty) {
      final shape = switch (mode) {
        CanvasInteraction.selectRect => SelectShape.rect,
        CanvasInteraction.selectEllipse => SelectShape.ellipse,
        _ => SelectShape.free,
      };
      // 起止两点即可定矩形/椭圆；自由曲线用全部轨迹点
      final List<(double, double)> pts = (mode == CanvasInteraction.selectFree)
          ? List<(double, double)>.from(_pts)
          : [_pts.first, _pts.last];
      ref.read(segmentProvider.notifier).grabCutSelect(shape, pts);
      // 框选完成回到浏览模式
      ref.read(interactionRequestProvider.notifier).state = CanvasInteraction.pan;
      ref.read(interactionProvider.notifier).state = CanvasInteraction.pan;
    }
    // 涂抹结束一笔：重置笔触连线起点，下一笔另起（不与本笔末尾连线）
    if (mode == CanvasInteraction.scribbleFg || mode == CanvasInteraction.scribbleBg) {
      ref.read(segmentProvider.notifier).endStroke();
    }
    _multiTouch = false;
    setState(() {
      _pts.clear();
      _selectDisplay.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    // 面板点「开始框选/涂抹」会写 interactionRequestProvider。这里同步消费：
    // 在渲染手势层之前就把 interaction 切过去，保证第一次按下就被当作框选，
    // 不会因为「按下时还是 pan、抬起才切换」而需要框两次。
    final requested = ref.watch(interactionRequestProvider);
    if (requested != ref.read(interactionProvider)) {
      // 在 build 阶段安全地同步状态（下一帧生效）
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (ref.read(interactionProvider) != requested) {
          ref.read(interactionProvider.notifier).state = requested;
        }
      });
    }
    final mode = ref.watch(interactionProvider);
    final viewMode = ref.watch(viewModeProvider);
    final selecting = mode != CanvasInteraction.pan;
    final cropping = mode == CanvasInteraction.crop;
    final scribbling = mode == CanvasInteraction.scribbleFg ||
        mode == CanvasInteraction.scribbleBg;
    // 裁剪框（图像像素），裁剪叠层据此重绘
    final cropRect = ref.watch(cropRectProvider);
    // 涂抹叠层读状态层的持久化显示缓冲（多笔/前景背景全程保留，不只当前一笔）。
    // watch 顶层 segment + version，scribbleAt 更新缓冲后 version+1 触发重绘。
    final seg = ref.watch(segmentProvider);
    ref.watch(segmentProvider.select((s) => s.scribbleVersion));

    final imageChild = Center(
      child: _ImageWithMask(working: widget.working, mode: viewMode),
    );

    return LayoutBuilder(builder: (context, constraints) {
      final box = Size(constraints.maxWidth, constraints.maxHeight);
      final imgRect = _imageRect(box);
      return InteractiveViewer(
        transformationController: widget.tx,
        minScale: 0.2,
        maxScale: 12.0,
        boundaryMargin: const EdgeInsets.all(double.infinity),
        // 选择/涂抹时禁用 InteractiveViewer 的手势（缩放平移），交给手势层
        panEnabled: !selecting,
        scaleEnabled: !selecting,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          // 瞬时手势：单指=涂抹/框选，双指=平移+捏合缩放
          onScaleStart: selecting ? (d) => _onScaleStart(d, box, mode) : null,
          onScaleUpdate: selecting ? (d) => _onScaleUpdate(d, box, mode) : null,
          onScaleEnd: selecting ? (d) => _onScaleEnd(d, mode) : null,
          child: Stack(
            fit: StackFit.expand,
            children: [
              imageChild,
              // 手势可视化叠层
              if (selecting)
                Positioned.fill(
                  child: IgnorePointer(
                    child: CustomPaint(
                      painter: cropping
                          ? _CropPainter(
                              box: cropRect == null
                                  ? null
                                  : _cropToDisplay(
                                      _normalizeRect(cropRect), imgRect),
                              imgRect: imgRect,
                            )
                          : scribbling
                          ? _ScribblePainter(
                              fg: seg.fgDisplay,
                              bg: seg.bgDisplay,
                              mw: seg.width,
                              mh: seg.height,
                              imgRect: imgRect,
                              workingW: widget.working.width,
                              brushRadiusImg: seg.brushRadius,
                            )
                          : _GesturePainter(
                              select: _selectDisplay,
                              mode: mode,
                            ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    });
  }
}

/// 手势轨迹可视化：框选画轮廓（矩形/椭圆/自由曲线）。
class _GesturePainter extends CustomPainter {
  final List<Offset> select; // 框选轨迹（显示坐标）
  final CanvasInteraction mode;
  _GesturePainter({
    required this.select,
    required this.mode,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // 框选：画轮廓
    if (select.length < 2) return;
    final stroke = Paint()
      ..color = const Color(0xFF3B82F6).withOpacity(0.9)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;
    final fill = Paint()
      ..color = const Color(0xFF3B82F6).withOpacity(0.12)
      ..style = PaintingStyle.fill;
    final a = select.first, b = select.last;
    final rect = Rect.fromPoints(a, b);
    switch (mode) {
      case CanvasInteraction.selectRect:
        canvas.drawRect(rect, fill);
        canvas.drawRect(rect, stroke);
        break;
      case CanvasInteraction.selectEllipse:
        canvas.drawOval(rect, fill);
        canvas.drawOval(rect, stroke);
        break;
      case CanvasInteraction.selectFree:
        final path = Path()..moveTo(select[0].dx, select[0].dy);
        for (var i = 1; i < select.length; i++) {
          path.lineTo(select[i].dx, select[i].dy);
        }
        canvas.drawPath(path, stroke);
        break;
      default:
        break;
    }
  }

  @override
  bool shouldRepaint(_GesturePainter old) => old.select.length != select.length;
}

/// 裁剪可视化：外部半透明遮罩（框内全透明清晰）+ 裁剪框 + 8 手柄。
/// box 为显示坐标 Rect（null=尚未框选，整图压暗提示）。
class _CropPainter extends CustomPainter {
  final Rect? box; // 裁剪框（显示坐标）
  final Rect imgRect; // 图像显示矩形（遮罩只罩图像区域）
  const _CropPainter({required this.box, required this.imgRect});

  @override
  void paint(Canvas canvas, Size size) {
    // 遮罩：整图半透明压暗，框内掏空（中心清晰、外部到图像边缘低透明）
    final dim = Paint()..color = const Color(0xFF000000).withOpacity(0.42);
    final maskPath = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(imgRect);
    if (box != null) maskPath.addRect(box!);
    canvas.drawPath(maskPath, dim);

    if (box == null) return;
    final b = box!;
    // 框边：白描边 + 蓝主线（深浅背景都清晰）
    final border = Paint()
      ..color = const Color(0xFFFFFFFF).withOpacity(0.9)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke;
    canvas.drawRect(b, border);
    final line = Paint()
      ..color = const Color(0xFF3B82F6).withOpacity(0.95)
      ..strokeWidth = 1.6
      ..style = PaintingStyle.stroke;
    canvas.drawRect(b, line);

    // 8 手柄：四角 + 四边中心（白底蓝边圆点，触屏加大）
    final handleFill = Paint()..color = const Color(0xFFFFFFFF);
    final handleStroke = Paint()
      ..color = const Color(0xFF3B82F6).withOpacity(0.95)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    final pts = <Offset>[
      b.topLeft, Offset(b.center.dx, b.top), b.topRight,
      Offset(b.left, b.center.dy), Offset(b.right, b.center.dy),
      b.bottomLeft, Offset(b.center.dx, b.bottom), b.bottomRight,
    ];
    for (final p in pts) {
      canvas.drawCircle(p, 7, handleFill);
      canvas.drawCircle(p, 7, handleStroke);
    }
  }

  @override
  bool shouldRepaint(_CropPainter old) => old.box != box || old.imgRect != imgRect;
}

/// 涂抹可视化：把状态层的 fg/bg 涂抹缓冲（计算域小图）按笔触尺寸画成半透明圆点。
/// 前景=红、背景=绿，多笔/两种颜色全程保留；迭代分割提交后缓冲清空，叠层随之清空。
class _ScribblePainter extends CustomPainter {
  final Uint8List? fg, bg; // 计算域小图（mw*mh）0/255
  final int mw, mh; // 缓冲尺寸（= mask 域 / 工作图域）
  final Rect imgRect; // 图像在叠层坐标系的显示矩形（BoxFit.contain）
  final int workingW; // 原图宽（px），用于把笔触半径换算成显示像素
  final double brushRadiusImg; // 笔触半径（原图像素）
  const _ScribblePainter({
    required this.fg,
    required this.bg,
    required this.mw,
    required this.mh,
    required this.imgRect,
    required this.workingW,
    required this.brushRadiusImg,
  });

  void _paintBuf(Canvas canvas, Uint8List? buf, Color color, double cellW, double cellH) {
    if (buf == null || mw <= 0 || mh <= 0) return;
    final p = Paint()..color = color;
    // 点的直径≈笔触直径（显示像素），保证「笔触粗细」可视化所见即所得
    final r = (brushRadiusImg * imgRect.width / workingW).clamp(cellW * 0.5, 40.0);
    for (var y = 0; y < mh; y++) {
      for (var x = 0; x < mw; x++) {
        if (buf[y * mw + x] == 0) continue;
        final cx = imgRect.left + (x + 0.5) * cellW;
        final cy = imgRect.top + (y + 0.5) * cellH;
        canvas.drawCircle(Offset(cx, cy), r, p);
      }
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    final cellW = imgRect.width / mw;
    final cellH = imgRect.height / mh;
    _paintBuf(canvas, bg, const Color(0xFF22C55E).withOpacity(0.5), cellW, cellH);
    _paintBuf(canvas, fg, const Color(0xFFEF4444).withOpacity(0.5), cellW, cellH);
  }

  @override
  bool shouldRepaint(_ScribblePainter old) =>
      !identical(old.fg, fg) || !identical(old.bg, bg) || old.imgRect != imgRect;
}
