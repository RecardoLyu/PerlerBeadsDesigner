import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../state/app_state.dart';
import '../../theme/candy_theme.dart';
import '../sheet/function_sheet.dart';
import '../widgets.dart';

/// 分割面板：迭代 GrabCut + 自动分割 + 形态学（对应桌面版分割三卡）
class SegmentPanel extends ConsumerStatefulWidget {
  const SegmentPanel({super.key});
  @override
  ConsumerState<SegmentPanel> createState() => _SegmentPanelState();
}

class _SegmentPanelState extends ConsumerState<SegmentPanel> {
  // GrabCut
  int _step = 0; // 0 初始分割 / 1 迭代分割
  int _shape = 0; // 0 矩形 / 1 椭圆 / 2 自由曲线
  late double _brushSize;
  int _brushType = 0; // 0 前景(红) / 1 背景(绿)
  // 自动分割
  late String _method;
  double _fgRatio = 0.4;
  double _superpixels = 150;
  // 形态学
  int _morphOp = 0;
  double _kernel = 5;
  int _kernelShape = 0;
  bool _initialized = false;

  @override
  Widget build(BuildContext context) {
    if (!_initialized) {
      final s = ref.read(settingsProvider);
      _brushSize = s.brushSize;
      _method = s.segMethod;
      _initialized = true;
    }
    final hasImage = ref.watch(imageProvider).hasImage;
    final seg = ref.watch(segmentProvider);
    final segBusy = seg.busy;
    final hasMask = seg.hasMask;
    final undoCount = seg.undoCount;
    final redoCount = seg.redoCount;
    final interaction = ref.watch(interactionProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const PanelTitle(icon: Icons.content_cut_rounded, title: '迭代 GrabCut'),
        CandyChips(options: const ['初始分割', '迭代分割'], selected: _step, onChanged: (i) => setState(() => _step = i)),
        const SizedBox(height: 9),
        if (_step == 0) ...[
          SelectRow<int>(label: '形状', value: _shape, items: const [(0, '矩形'), (1, '椭圆'), (2, '自由曲线')],
            leading: (v) => ShapeGlyph(const [ShapeGlyphKind.rect, ShapeGlyphKind.ellipse, ShapeGlyphKind.freehand][v.clamp(0, 2)]),
            onChanged: (v) => setState(() => _shape = v)),
          CandyButton(
            label: interaction == CanvasInteraction.pan ? '开始框选' : '框选中…（在画布拖动）',
            primary: false,
            onPressed: hasImage
                ? () {
                    cancelCanvasInteraction(ref); // 进框选前取消裁剪/其它交互
                    final m = switch (_shape) {
                      0 => CanvasInteraction.selectRect,
                      1 => CanvasInteraction.selectEllipse,
                      _ => CanvasInteraction.selectFree,
                    };
                    ref.read(interactionRequestProvider.notifier).state = m;
                    ref.read(interactionProvider.notifier).state = m;
                    ref.read(statusMessageProvider.notifier).state = '请在画布上拖动框选目标区域';
                    ref.read(sheetCollapseRequestProvider.notifier).state++;
                  }
                : null,
          ),
        ] else ...[
          SliderRow(label: '笔触粗细', value: _brushSize, min: 4, max: 40, decimals: 0, onChanged: (v) {
            setState(() => _brushSize = v);
            ref.read(segmentProvider.notifier).setBrushRadius(v / 2);
          }),
          // 前景/背景选择：圆形色点直观表示当前笔触颜色与粗细（替代「(红)/(绿)」文字）
          // 涂抹进行中切换时，直接实时切 interaction（不清缓冲）：
          // fg/bg 缓冲本就独立累加，先画前景再画背景两色可同时保留渲染。
          // （否则只在面板本地改 _brushType，画布仍按旧色画；用户再点「开始涂抹」又会
          //   beginScribble→clearScribbles 把已画的另一色清掉 —— 这正是「两色无法共存」的 bug）
          _BrushPicker(
            type: _brushType,
            brushSize: _brushSize,
            onChanged: (i) {
              setState(() => _brushType = i);
              final cur = ref.read(interactionProvider);
              if (cur == CanvasInteraction.scribbleFg || cur == CanvasInteraction.scribbleBg) {
                final m = i == 0 ? CanvasInteraction.scribbleFg : CanvasInteraction.scribbleBg;
                ref.read(interactionRequestProvider.notifier).state = m;
                ref.read(interactionProvider.notifier).state = m;
                ref.read(statusMessageProvider.notifier).state =
                    i == 0 ? '涂抹「属于目标」的区域（红）' : '涂抹「不属于目标」的区域（绿）';
              }
            },
          ),
          const SizedBox(height: 9),
          CandyButton(
            label: interaction == CanvasInteraction.pan ? '开始涂抹' : '涂抹中…（在画布拖动）',
            primary: false,
            onPressed: (hasImage && seg.hasGrabCutSession)
                ? () {
                    cancelCanvasInteraction(ref); // 进涂抹前取消裁剪/其它交互
                    final segN = ref.read(segmentProvider.notifier);
                    segN.setBrushRadius(_brushSize / 2);
                    // 进涂抹：清空上一轮痕迹 + 默认切到高亮叠加画布
                    segN.beginScribble();
                    final m = _brushType == 0 ? CanvasInteraction.scribbleFg : CanvasInteraction.scribbleBg;
                    ref.read(interactionRequestProvider.notifier).state = m;
                    ref.read(interactionProvider.notifier).state = m;
                    ref.read(statusMessageProvider.notifier).state =
                        _brushType == 0 ? '涂抹「属于目标」的区域（红）' : '涂抹「不属于目标」的区域（绿）';
                    ref.read(sheetCollapseRequestProvider.notifier).state++;
                  }
                : null,
          ),
          const SizedBox(height: 9),
          CandyButton(
            label: segBusy ? '迭代中…' : '迭代分割',
            onPressed: (seg.hasGrabCutSession && !segBusy)
                ? () async {
                    // 退出涂抹模式并提交
                    ref.read(interactionRequestProvider.notifier).state = CanvasInteraction.pan;
                    ref.read(interactionProvider.notifier).state = CanvasInteraction.pan;
                    await ref.read(segmentProvider.notifier).commitRefine();
                  }
                : null,
          ),
        ],

        const PanelDivider(),
        const PanelTitle(icon: Icons.auto_awesome_rounded, title: '自动分割'),
        SelectRow<String>(label: '方法', value: _method, items: const [
          ('grabcut_rect', 'GrabCut矩形'), ('watershed', '分水岭'), ('otsu', 'Otsu'), ('slic', 'SLIC'),
        ], onChanged: (v) => setState(() => _method = v)),
        if (_method == 'watershed')
          SliderRow(label: '前景比例', value: _fgRatio, min: 0.1, max: 0.9, onChanged: (v) => setState(() => _fgRatio = v)),
        if (_method == 'slic')
          SliderRow(label: '超像素数', value: _superpixels, min: 50, max: 400, decimals: 0, onChanged: (v) => setState(() => _superpixels = v)),
        CandyButton(
          label: segBusy ? '分割中…' : '执行分割',
          onPressed: (hasImage && !segBusy)
              ? () => ref.read(segmentProvider.notifier).autoSegment(
                    _method,
                    fgRatio: _fgRatio,
                    superpixels: _superpixels.round(),
                  )
              : null,
        ),

        const PanelDivider(),
        const PanelTitle(icon: Icons.blur_circular_rounded, title: '形态学'),
        SelectRow<int>(label: '操作', value: _morphOp, items: const [(0, '开运算'), (1, '闭运算'), (2, '腐蚀'), (3, '膨胀')], onChanged: (v) => setState(() => _morphOp = v)),
        SliderRow(label: '核大小', value: _kernel, min: 1, max: 21, decimals: 0, onChanged: (v) => setState(() => _kernel = v)),
        SelectRow<int>(label: '结构元素', value: _kernelShape, items: const [(0, '椭圆'), (1, '矩形'), (2, '十字'), (3, '垂直线'), (4, '水平线'), (5, '菱形')],
          leading: (v) => ShapeGlyph(const [
            ShapeGlyphKind.ellipse, ShapeGlyphKind.rect, ShapeGlyphKind.cross,
            ShapeGlyphKind.vline, ShapeGlyphKind.hline, ShapeGlyphKind.diamond,
          ][v.clamp(0, 5)]),
          onChanged: (v) => setState(() => _kernelShape = v)),
        CandyButton(
          label: '应用形态学',
          onPressed: (hasMask && !segBusy)
              ? () => ref.read(segmentProvider.notifier).applyMorph(
                    _morphOp, _kernel.round(), _kernelShape)
              : null,
        ),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: CandyButton(label: '↺ 撤销', primary: false,
              onPressed: undoCount > 0 ? () => ref.read(segmentProvider.notifier).undo() : null)),
          const SizedBox(width: 9),
          Expanded(child: CandyButton(label: '↻ 重做', primary: false,
              onPressed: redoCount > 0 ? () => ref.read(segmentProvider.notifier).redo() : null)),
        ]),
      ],
    );
  }
}

/// 前景/背景笔触选择器：圆形色点直观表示当前笔触颜色与粗细。
/// 替代原来的「前景(红)/背景(绿)」文字 chip —— 圆点直径随笔触粗细变化，所见即所得。
class _BrushPicker extends StatelessWidget {
  final int type; // 0 前景 / 1 背景
  final double brushSize; // 笔触直径（px）
  final ValueChanged<int> onChanged;
  const _BrushPicker({required this.type, required this.brushSize, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    // 圆点显示直径：把笔触直径(4~40px)映射到一个好看的视觉范围(10~26)
    final dot = (8 + brushSize / 40 * 18).clamp(10.0, 26.0);
    Widget opt(int i, Color color, String label) {
      final on = type == i;
      return Expanded(
        child: GestureDetector(
          onTap: () => onChanged(i),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: BoxDecoration(
              color: on ? c.surfaceStrong : c.muted,
              border: Border.all(
                color: on ? color : c.border,
                width: on ? 1.8 : 1,
              ),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  width: dot, height: dot,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: color.withOpacity(0.85),
                    border: Border.all(color: Colors.white.withOpacity(0.7), width: 1.2),
                  ),
                ),
                const SizedBox(width: 8),
                Text(label,
                    style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700,
                        color: on ? c.foregroundStrong : c.mutedFg)),
              ],
            ),
          ),
        ),
      );
    }

    return Row(children: [
      opt(0, const Color(0xFFEF4444), '前景'),
      const SizedBox(width: 8),
      opt(1, const Color(0xFF22C55E), '背景'),
    ]);
  }
}
