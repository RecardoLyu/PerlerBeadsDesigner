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
  late final TextEditingController _nameCtrl;
  int _resIndex = 1; // 默认 2K
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: ref.read(exportNameProvider));
    // 源图变化时跟随文件名（仅当输入框还是旧源名/默认值，不覆盖用户手改）
    ref.listenManual<String>(exportNameProvider, (prev, next) {
      if (_nameCtrl.text != next) _nameCtrl.text = next;
    });
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

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
    // 切全局 busy：颜文字跳动 + 指示灯变红，与「导出中…」按钮同步生效。
    ref.read(patternProvider.notifier).setBusy(true, '正在导出图纸 PNG …');
    // 让出一帧，保证 busy UI 立刻重绘，再做 4K 重渲染/PNG 编码。
    await Future.delayed(Duration.zero);
    try {
      final widthPx = ExportService.resolutions[_resIndex].$2;
      final name = _nameCtrl.text.trim();
      final saved = await ExportService.saveChart(
        chart,
        widthPx,
        name: name.isEmpty ? 'pattern' : name,
      );
      ref.read(statusMessageProvider.notifier).state = '已导出：$saved';
    } catch (e) {
      ref.read(statusMessageProvider.notifier).state = '导出失败：$e';
    } finally {
      ref.read(patternProvider.notifier).setBusy(false);
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
          Expanded(child: TextFormField(
            controller: _nameCtrl,
            onChanged: (s) => ref.read(exportNameProvider.notifier).state = s,
          )),
        ]),
        Row(children: [
          const SizedBox(width: 58),
          Expanded(child: InkWell(
            onTap: () => ref.read(showChartTitleProvider.notifier).state =
                !ref.read(showChartTitleProvider),
            child: Row(children: [
              Checkbox(
                value: ref.watch(showChartTitleProvider),
                onChanged: (v) =>
                    ref.read(showChartTitleProvider.notifier).state = v ?? false,
              ),
              const Expanded(child: Text('在图纸上显示文件名', style: TextStyle(fontSize: 12.5))),
            ]),
          )),
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
        Row(children: [
          const SizedBox(width: 58, child: Text('豆子风格', style: TextStyle(fontSize: 12.5))),
          Expanded(
            child: CandyChips(
              options: const ['真实风', '图纸风'],
              selected: ref.watch(beadStyleProvider) == 'real' ? 0 : 1,
              onChanged: (i) {
                ref.read(beadStyleProvider.notifier).state =
                    i == 0 ? 'real' : 'square';
                // 已有图纸则按新风格重渲染（预览/导出共用 ChartPainter）
                if (ref.read(patternProvider).chartImage != null) {
                  ref.read(patternProvider.notifier).generate();
                }
              },
            ),
          ),
        ]),
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
          // 宽度随色号长度自适应，长码（如 80-15179）也能单行放下
          constraints: const BoxConstraints(minWidth: 22, minHeight: 22),
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
          alignment: Alignment.center,
          decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(999)),
          child: Text(code, style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w800, color: fg)),
        ),
        const SizedBox(width: 7),
        Text('×$count', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.foreground)),
      ]),
    );
  }
}
