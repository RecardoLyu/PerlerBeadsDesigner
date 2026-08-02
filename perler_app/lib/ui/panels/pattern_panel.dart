import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../state/app_state.dart';
import '../sheet/function_sheet.dart';
import '../widgets.dart';

/// 图纸面板：图纸参数 + 生成（对应桌面版图纸参数卡）
class PatternPanel extends ConsumerStatefulWidget {
  const PatternPanel({super.key});
  @override
  ConsumerState<PatternPanel> createState() => _PatternPanelState();
}

class _PatternPanelState extends ConsumerState<PatternPanel> {
  double _w = 104, _h = 104;
  bool _keepRatio = true;
  double _maxColors = 0;
  double _salience = 1.0;
  String _metric = 'ciede2000';
  bool _dither = false;
  double _ditherStrength = 1.0;
  bool _icm = false;
  double _icmSmooth = 0.5;
  bool _useMask = true;
  String _maskBg = 'none';

  /// 图纸高（豆）：勾选「保持图像比例」时按当前图像宽高比由宽度推算。
  int _gridH(int gw) {
    if (!_keepRatio) return _h.round().clamp(1, 512);
    final img = ref.read(imageProvider).working;
    if (img == null || img.width <= 0) return gw;
    return (gw * img.height / img.width).round().clamp(1, 512);
  }

  /// 把图纸尺寸写入 patternGridProvider（分割下采样目标据此计算）。
  void _syncGrid() {
    final gw = _w.round().clamp(1, 512);
    ref.read(patternGridProvider.notifier).state = (gw, _gridH(gw));
  }

  /// 生成图纸：读取全部字段调 PatternNotifier.generate，成功后收起抽屉露图纸。
  Future<void> _generate() async {
    final gw = _w.round().clamp(1, 512);
    final gh = _gridH(gw);
    await ref.read(patternProvider.notifier).generate(
          gw: gw,
          gh: gh,
          colorLimit: _maxColors.round() <= 0 ? null : _maxColors.round(),
          salience: _salience,
          metric: _metric,
          dither: _dither,
          ditherStrength: _ditherStrength,
          icmSmooth: _icm ? _icmSmooth : 0.0,
          useMask: _useMask,
          maskBg: _maskBg,
        );
    // 生成成功（有图纸）后收起 sheet，立刻看到图纸
    if (ref.read(patternProvider).hasPattern) {
      ref.read(sheetCollapseRequestProvider.notifier).state++;
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasImage = ref.watch(imageProvider.select((s) => s.hasImage));
    final busy = ref.watch(patternProvider.select((s) => s.busy));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const PanelTitle(icon: Icons.grid_on_rounded, title: '图纸参数'),
        Row(children: [
          const SizedBox(width: 58, child: Text('宽度(豆)', style: TextStyle(fontSize: 12.5))),
          Expanded(child: TextFormField(initialValue: '104', keyboardType: TextInputType.number, onChanged: (s) { _w = double.tryParse(s) ?? _w; _syncGrid(); })),
          const SizedBox(width: 8),
          const Text('高', style: TextStyle(fontSize: 12.5)),
          const SizedBox(width: 8),
          Expanded(child: TextFormField(
            initialValue: '104',
            keyboardType: TextInputType.number,
            enabled: !_keepRatio,
            decoration: InputDecoration(
              hintText: _keepRatio ? '按图像比例自动' : null,
              hintStyle: const TextStyle(fontSize: 12),
            ),
            onChanged: (s) { _h = double.tryParse(s) ?? _h; _syncGrid(); },
          )),
        ]),
        CheckRow(label: '保持图像比例', value: _keepRatio, onChanged: (v) => setState(() { _keepRatio = v; _syncGrid(); })),        Row(children: [
          const SizedBox(width: 58, child: Text('颜色上限', style: TextStyle(fontSize: 12.5))),
          Expanded(child: TextFormField(initialValue: '0', keyboardType: TextInputType.number, onChanged: (s) => _maxColors = double.tryParse(s) ?? 0)),
          const SizedBox(width: 8),
          Text('0 = 不限制', style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurface.withOpacity(0.5))),
        ]),
        SliderRow(label: '细节保留', value: _salience, min: 0, max: 2, decimals: 1, onChanged: (v) => setState(() => _salience = v)),
        SelectRow<String>(label: '颜色度量', value: _metric, items: const [
          ('weighted', '加权距离'), ('euclidean', '欧氏距离'), ('lab', 'Lab色空'), ('ciede76', 'CIE76'), ('ciede2000', 'CIEDE2000'),
        ], onChanged: (v) => setState(() => _metric = v)),
        CheckRow(label: '抖动', value: _dither, onChanged: (v) => setState(() => _dither = v)),
        if (_dither) SliderRow(label: '抖动强度', value: _ditherStrength, min: 0, max: 1, onChanged: (v) => setState(() => _ditherStrength = v)),
        CheckRow(label: '高阶优化(ICM)', value: _icm, onChanged: (v) => setState(() => _icm = v)),
        if (_icm) SliderRow(label: 'ICM平滑', value: _icmSmooth, min: 0.1, max: 1, onChanged: (v) => setState(() => _icmSmooth = v)),
        CheckRow(label: '使用分割 Mask', value: _useMask, onChanged: (v) => setState(() => _useMask = v)),
        SelectRow<String>(label: 'Mask背景', value: _maskBg, items: const [('none', '淡化'), ('white', '纯白'), ('black', '纯黑')], onChanged: (v) => setState(() => _maskBg = v)),
        const SizedBox(height: 8),
        CandyButton(
          label: busy ? '生成中…' : '生成图纸',
          icon: Icons.auto_fix_high_rounded,
          onPressed: (hasImage && !busy) ? _generate : null,
        ),
      ],
    );
  }
}
