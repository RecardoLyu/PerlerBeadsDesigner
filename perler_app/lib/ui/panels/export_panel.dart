import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../services/export_service.dart';
import '../../state/app_state.dart';
import '../../theme/candy_theme.dart';
import '../widgets.dart';

/// 导出面板：一键把图纸 PNG 存到相册 + BOM（对应桌面版导出+BOM 两卡）。
/// 移动端不再让用户选目录/选格式：固定导出 PNG 到相册「Pictures/拼豆图纸」，
/// 分辨率三档（1080P / 2K / 4K），不提供缩放滑块与 PDF 开关。
class ExportPanel extends ConsumerStatefulWidget {
  const ExportPanel({super.key});
  @override
  ConsumerState<ExportPanel> createState() => _ExportPanelState();
}

class _ExportPanelState extends ConsumerState<ExportPanel> {
  String _name = 'pattern';
  int _resIndex = 1; // 默认 2K
  bool _saving = false;

  /// 由 hex('#RRGGBB') 解析颜色；失败回退灰色。
  Color _parseHex(String hex) {
    try {
      return Color(0xFF000000 | int.parse(hex.substring(1), radix: 16));
    } catch (_) {
      return const Color(0xFF808080);
    }
  }

  Future<void> _export() async {
    final chart = ref.read(patternProvider).chartImage;
    if (chart == null) {
      ref.read(statusMessageProvider.notifier).state = '请先在「图纸」页生成图纸';
      return;
    }
    setState(() => _saving = true);
    ref.read(statusMessageProvider.notifier).state = '正在导出图纸 PNG …';
    try {
      final widthPx = ExportService.resolutions[_resIndex].$2;
      final saved = await ExportService.saveChart(
        chart,
        widthPx,
        name: _name.trim().isEmpty ? 'pattern' : _name.trim(),
      );
      ref.read(statusMessageProvider.notifier).state = '已导出：$saved';
    } catch (e) {
      ref.read(statusMessageProvider.notifier).state = '导出失败：$e';
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final pat = ref.watch(patternProvider);
    // 显式 watch version，确保新图纸生成后 BOM 区刷新
    ref.watch(patternProvider.select((s) => s.version));
    final bom = pat.bom;
    final hasChart = pat.chartImage != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const PanelTitle(icon: Icons.file_download_outlined, title: '导出图纸', sub: '保存为 PNG 到相册「Pictures/拼豆图纸」'),
        Row(children: [
          const SizedBox(width: 58, child: Text('文件名', style: TextStyle(fontSize: 12.5))),
          Expanded(child: TextFormField(initialValue: _name, onChanged: (s) => _name = s)),
        ]),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(children: [
            const SizedBox(width: 58, child: Text('分辨率', style: TextStyle(fontSize: 12.5))),
            Expanded(
              child: CandyChips(
                options: ExportService.resolutions.map((r) => r.$1).toList(),
                selected: _resIndex,
                onChanged: (i) => setState(() => _resIndex = i),
              ),
            ),
          ]),
        ),
        const SizedBox(height: 8),
        CandyButton(
          label: _saving ? '导出中…' : '导出 PNG 到相册',
          icon: Icons.bolt_rounded,
          onPressed: (hasChart && !_saving) ? _export : null,
        ),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            hasChart ? '将按所选分辨率保存当前图纸。' : '请先在「图纸」页生成图纸。',
            style: TextStyle(fontSize: 11.5, color: c.mutedFg),
          ),
        ),

        const PanelDivider(),
        const PanelTitle(icon: Icons.list_alt_rounded, title: '物料清单 (BOM)', sub: '生成图纸后显示所需豆子颜色与数量'),
        if (bom.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text('尚未生成图纸 · 在「图纸」页点「生成图纸」',
                style: TextStyle(fontSize: 12, color: c.mutedFg)),
          )
        else ...[
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: bom.map((e) {
              final color = _parseHex(e.hex);
              final lum = 0.299 * color.red + 0.587 * color.green + 0.114 * color.blue;
              final fg = lum > 128 ? const Color(0xFF1A1A1A) : Colors.white;
              return _BomChip(code: e.code, color: color, fg: fg, count: e.count);
            }).toList(),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('共 ${pat.totalBeads} 豆 · ${bom.length} 种颜色',
                style: TextStyle(fontSize: 11.5, color: c.mutedFg)),
          ),
        ],
      ],
    );
  }
}

class _BomChip extends StatelessWidget {
  final String code;
  final Color color, fg;
  final int count;
  const _BomChip({required this.code, required this.color, required this.fg, required this.count});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Container(
      padding: const EdgeInsets.fromLTRB(4, 4, 12, 4),
      decoration: BoxDecoration(color: c.muted, border: Border.all(color: c.border), borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 20, height: 20,
          alignment: Alignment.center,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          child: Text(code, style: TextStyle(fontSize: 8.5, fontWeight: FontWeight.w800, color: fg)),
        ),
        const SizedBox(width: 7),
        Text('×$count', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.foreground)),
      ]),
    );
  }
}
