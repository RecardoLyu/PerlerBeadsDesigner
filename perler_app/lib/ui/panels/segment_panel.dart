import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../state/app_state.dart';
import '../../algo/cv_ops.dart';
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
  double _brushSize = 12;
  int _brushType = 0; // 0 前景(红) / 1 背景(绿)
  // 自动分割
  String _method = 'watershed';
  double _fgRatio = 0.4;
  double _superpixels = 150;
  // 形态学
  int _morphOp = 0;
  double _kernel = 5;
  int _kernelShape = 0;

  // 临时：dartcv4 native 连通性自检（M2 完成后移除）
  void _testCv() {
    try {
      final ok = CvOps.selfTest();
      ref.read(statusMessageProvider.notifier).state =
          ok ? '✅ dartcv4 可用 (OpenCV native 正常)' : '⚠️ dartcv4 返回异常';
    } catch (e) {
      ref.read(statusMessageProvider.notifier).state = '❌ dartcv4 调用抛错: $e';
    }
  }

  @override
  Widget build(BuildContext context) {
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
        // 临时诊断按钮（M2 完成后移除）
        CandyButton(label: '🔍 诊断 OpenCV(dartcv4)', primary: false, onPressed: _testCv),
        const SizedBox(height: 8),

        const PanelTitle(icon: Icons.content_cut_rounded, title: '迭代 GrabCut'),
        CandyChips(options: const ['初始分割', '迭代分割'], selected: _step, onChanged: (i) => setState(() => _step = i)),
        const SizedBox(height: 9),
        if (_step == 0) ...[
          SelectRow<int>(label: '形状', value: _shape, items: const [(0, '矩形 ▭'), (1, '椭圆 ⬭'), (2, '自由曲线 ✎')], onChanged: (v) => setState(() => _shape = v)),
          CandyButton(
            label: interaction == CanvasInteraction.pan ? '开始框选' : '框选中…（在画布拖动）',
            primary: false,
            onPressed: hasImage
                ? () {
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
          CandyChips(options: const ['前景(红)', '背景(绿)'], selected: _brushType, onChanged: (i) => setState(() => _brushType = i)),
          const SizedBox(height: 9),
          CandyButton(
            label: interaction == CanvasInteraction.pan ? '开始涂抹' : '涂抹中…（在画布拖动）',
            primary: false,
            onPressed: (hasImage && seg.hasGrabCutSession)
                ? () {
                    final segN = ref.read(segmentProvider.notifier);
                    segN.clearScribbles();
                    segN.setBrushRadius(_brushSize / 2);
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
        SelectRow<int>(label: '结构元素', value: _kernelShape, items: const [(0, '椭圆 ●'), (1, '矩形 ■'), (2, '十字 ┼'), (3, '垂直线 │'), (4, '水平线 ─'), (5, '菱形 ◆')], onChanged: (v) => setState(() => _kernelShape = v)),
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
