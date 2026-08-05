import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../algo/quantizer.dart';
import '../../services/export_service.dart';
import '../../services/image_loader.dart';
import '../../state/app_state.dart';
import '../../theme/candy_theme.dart';
import '../widgets.dart';

/// 图纸画板面板：工具条 + 圆环编号豆色横滚条 + 参考底图 + 导出（底部「屏幕下方」）。
/// 画布实时绘制在 BoardCanvas（主预览区）。
class BoardPanel extends ConsumerStatefulWidget {
  const BoardPanel({super.key});
  @override
  ConsumerState<BoardPanel> createState() => _BoardPanelState();
}

class _BoardPanelState extends ConsumerState<BoardPanel> {
  int _resIndex = 1; // 默认 2K
  bool _saving = false;
  late final TextEditingController _nameCtrl;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: 'board');
    // 首次进入确保画板已建
    Future.microtask(() => ref.read(boardProvider.notifier).ensure());
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  Color _hex(String hex) =>
      Color(0xFF000000 | int.parse(hex.substring(1), radix: 16));

  Future<void> _switchSize(int size) async {
    final ok = await _confirm('切换到 $size×$size 将清空当前画板，确定？');
    if (ok) await ref.read(boardProvider.notifier).newBoard(size, ref.read(boardProvider).brand);
  }

  Future<void> _switchBrand(String brand) async {
    final ok = await _confirm('切换拼豆品牌将清空当前画板（色号体系不同），确定？');
    if (ok) await ref.read(boardProvider.notifier).newBoard(ref.read(boardProvider).size, brand);
  }

  Future<bool> _confirm(String msg) async {
    final r = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        content: Text(msg),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定')),
        ],
      ),
    );
    return r ?? false;
  }

  Future<void> _importBase() async {
    final res = await ImageLoader.pickFromGallery();
    if (res == null) {
      ref.read(statusMessageProvider.notifier).state = '未选择图像';
      return;
    }
    // 整图导入（不再裁正方形），默认等比例铺满画板（超出裁切）并居中
    final img = await rgbToUiImage(res.rgb, res.width, res.height);
    ref.read(boardProvider.notifier).setBase(img);
    ref.read(statusMessageProvider.notifier).state = '底图已铺满画板（点「调整底图」可缩放/移动）';
  }

  Future<void> _export() async {
    final b = ref.read(boardProvider);
    if (!b.hasBoard || b.grid.every((c) => c == null)) {
      ref.read(statusMessageProvider.notifier).state = '画板为空，请先绘制';
      return;
    }
    setState(() => _saving = true);
    ref.read(statusMessageProvider.notifier).state = '正在导出图纸 PNG …';
    try {
      final chart = await ref.read(boardProvider.notifier).renderChart(
          title: _nameCtrl.text.trim().isEmpty ? null : _nameCtrl.text.trim());
      final widthPx = ExportService.resolutions[_resIndex].$2;
      final saved = await ExportService.saveChart(chart, widthPx,
          name: _nameCtrl.text.trim().isEmpty ? 'board' : _nameCtrl.text.trim());
      chart.dispose();
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
    final b = ref.watch(boardProvider);
    ref.watch(boardProvider.select((s) => s.version));
    final n = ref.read(boardProvider.notifier);
    final bom = n.bom();
    final colors = b.palette?.colors ?? const <BeadColor>[];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ---- 色板（图纸画板栏上方，绘制中快捷选色）----
        const PanelTitle(
            icon: Icons.palette_outlined, title: '色板', sub: '实心色块，点上即选为当前豆色'),
        SelectRow<String>(
          label: '拼豆品牌',
          value: b.brand,
          items: Palette.brandLabels.entries.map((e) => (e.key, e.value)).toList(),
          onChanged: _switchBrand,
        ),
        const SizedBox(height: 6),
        // 实心圆形色块横滚
        SizedBox(
          height: 64,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: colors.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, i) {
              final col = colors[i];
              final sel = col.code == b.color;
              final color = _hex(col.hex);
              return GestureDetector(
                onTap: () => n.setColor(col.code),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 36, height: 36,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: color,
                        border: Border.all(
                          color: sel
                              ? Theme.of(context).colorScheme.primary
                              : Colors.transparent,
                          width: 2.5,
                        ),
                        boxShadow: [
                          BoxShadow(
                              color: Colors.black.withOpacity(0.12),
                              blurRadius: 3, offset: const Offset(0, 1)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(col.code,
                        style: TextStyle(
                            fontSize: 8.5,
                            fontWeight: FontWeight.w800,
                            color: sel
                                ? Theme.of(context).colorScheme.primary
                                : c.mutedFg)),
                  ],
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 4),
        Text('当前：${b.color ?? '—'}',
            style: TextStyle(fontSize: 11.5, color: c.mutedFg)),

        const PanelDivider(),

        // ---- 图纸画板（规格/工具/笔触）----
        const PanelTitle(
            icon: Icons.brush_rounded, title: '图纸画板', sub: '自由绘制拼豆图纸（单指绘制 · 双指缩放平移）'),

        // ---- 规格 ----
        Row(children: [
          const SizedBox(width: 58, child: Text('规格', style: TextStyle(fontSize: 12.5))),
          Expanded(
            child: CandyChips(
              options: const ['52×52', '104×104'],
              selected: b.size == 52 ? 0 : 1,
              onChanged: (i) => _switchSize(i == 0 ? 52 : 104),
            ),
          ),
        ]),

        // ---- 工具条 ----
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(children: [
            const SizedBox(width: 58, child: Text('工具', style: TextStyle(fontSize: 12.5))),
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [
                  _toolBtn(BoardTool.pen, Icons.edit_rounded, '画笔', b, n),
                  _toolBtn(BoardTool.eraser, Icons.auto_fix_off_rounded, '橡皮擦', b, n),
                  _toolBtn(BoardTool.fill, Icons.format_color_fill_rounded, '填充', b, n),
                  _toolBtn(BoardTool.rect, Icons.crop_square_rounded, '框选填充', b, n),
                  const SizedBox(width: 6),
                  _actBtn(Icons.undo_rounded, '撤销', b.canUndo, n.undoOp),
                  _actBtn(Icons.redo_rounded, '重做', b.canRedo, n.redoOp),
                  _actBtn(Icons.delete_outline_rounded, '清空画板', b.hasBoard, () async {
                    if (await _confirm('清空整块画板？（可撤销）')) n.clearBoard();
                  }),
                ]),
              ),
            ),
          ]),
        ),

        // ---- 笔触粗细 ----
        SliderRow(
          label: '笔触粗细',
          value: b.brush.toDouble(),
          min: 1, max: 3, decimals: 0,
          onChanged: (v) => n.setBrush(v.round()),
        ),

        const PanelDivider(),

        // ---- 参考底图 ----
        const PanelTitle(icon: Icons.image_outlined, title: '参考底图', sub: '高透明叠加在豆之下，不干扰绘制'),
        Row(children: [
          Expanded(
            child: CandyButton(
              label: b.baseImage == null ? '上传底图' : '更换底图…',
              icon: Icons.add_photo_alternate_outlined,
              primary: false, compact: true,
              onPressed: _importBase,
            ),
          ),
          if (b.baseImage != null) ...[
            const SizedBox(width: 8),
            Expanded(
              child: CandyButton(
                label: '清除', icon: Icons.close_rounded,
                primary: false, compact: true,
                onPressed: () => n.clearBase(),
              ),
            ),
          ],
        ]),
        if (b.baseImage != null) ...[
          const SizedBox(height: 8),
          // 调整底图：进入后切【取消】【保存调整】，双指缩放/拖动底图，画布锁定
          if (!b.baseAdjusting)
            CandyButton(
              label: '调整底图', icon: Icons.open_with_rounded,
              primary: false, compact: true,
              onPressed: () => n.enterBaseAdjust(),
            )
          else ...[
            Row(children: [
              Expanded(
                child: CandyButton(
                  label: '取消', icon: Icons.close_rounded,
                  primary: false, compact: true,
                  onPressed: () => n.cancelBaseAdjust(),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: CandyButton(
                  label: '保存调整', icon: Icons.check_rounded,
                  primary: true, compact: true,
                  onPressed: () => n.saveBaseAdjust(),
                ),
              ),
            ]),
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('调整中：双指捏合缩放底图 · 拖动平移底图 · 画板缩放已锁定',
                  style: TextStyle(fontSize: 11, color: c.mutedFg)),
            ),
          ],
          CheckRow(label: '显示底图', value: b.baseVisible, onChanged: (v) => n.setBaseVisible(v)),
          SliderRow(
            label: '不透明度',
            value: b.baseOpacity, min: 0.1, max: 1.0, decimals: 2,
            onChanged: (v) => n.setBaseOpacity(v),
          ),
        ],

        const PanelDivider(),

        // ---- 导出 ----
        const PanelTitle(icon: Icons.file_download_outlined, title: '导出图纸', sub: '保存 PNG 到相册「Pictures/拼豆图纸」'),
        Row(children: [
          const SizedBox(width: 58, child: Text('风格', style: TextStyle(fontSize: 12.5))),
          Expanded(
            child: CandyChips(
              options: const ['真实风', '图纸风'],
              selected: b.style == 'real' ? 0 : 1,
              onChanged: (i) => n.setStyle(i == 0 ? 'real' : 'square'),
            ),
          ),
        ]),
        Row(children: [
          const SizedBox(width: 58, child: Text('文件名', style: TextStyle(fontSize: 12.5))),
          Expanded(child: TextFormField(controller: _nameCtrl)),
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
        CandyButton(
          label: _saving ? '导出中…' : '导出 PNG + BOM',
          icon: Icons.bolt_rounded,
          onPressed: _saving ? null : _export,
        ),

        const PanelDivider(),

        // ---- BOM ----
        const PanelTitle(icon: Icons.list_alt_rounded, title: '物料清单 (BOM)', sub: '绘制后实时统计所需豆子'),
        if (bom.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text('尚未绘制', style: TextStyle(fontSize: 12, color: c.mutedFg)),
          )
        else ...[
          Wrap(
            spacing: 8, runSpacing: 8,
            children: bom.map((e) {
              final color = _hex(e.hex);
              final lum = 0.299 * color.red + 0.587 * color.green + 0.114 * color.blue;
              final fg = lum > 128 ? const Color(0xFF1A1A1A) : Colors.white;
              return Container(
                padding: const EdgeInsets.fromLTRB(4, 4, 12, 4),
                decoration: BoxDecoration(
                    color: c.muted, border: Border.all(color: c.border),
                    borderRadius: BorderRadius.circular(999)),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(
                    constraints: const BoxConstraints(minWidth: 22, minHeight: 22),
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(999)),
                    child: Text(e.code, style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w800, color: fg)),
                  ),
                  const SizedBox(width: 7),
                  Text('×${e.count}', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.foreground)),
                ]),
              );
            }).toList(),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('共 ${n.totalBeads} 豆 · ${bom.length} 种颜色',
                style: TextStyle(fontSize: 11.5, color: c.mutedFg)),
          ),
        ],
      ],
    );
  }

  Widget _toolBtn(BoardTool t, IconData icon, String tip, BoardState b, BoardNotifier n) {
    final on = b.tool == t;
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: Tooltip(
        message: tip,
        child: GestureDetector(
          onTap: () => n.setTool(t),
          child: Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              gradient: on ? candyPrimaryGradient(context) : null,
              color: on ? null : c.surface,
              border: on ? null : Border.all(color: c.border),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(icon, size: 18, color: on ? Colors.white : c.foreground),
          ),
        ),
      ),
    );
  }

  Widget _actBtn(IconData icon, String tip, bool enabled, VoidCallback onTap) {
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: Tooltip(
        message: tip,
        child: GestureDetector(
          onTap: enabled ? onTap : null,
          child: Opacity(
            opacity: enabled ? 1 : 0.4,
            child: Container(
              width: 40, height: 40,
              decoration: BoxDecoration(
                color: c.surface,
                border: Border.all(color: c.border),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Icon(icon, size: 18, color: c.foreground),
            ),
          ),
        ),
      ),
    );
  }
}
