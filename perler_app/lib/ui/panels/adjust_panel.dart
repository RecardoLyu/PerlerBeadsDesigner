import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../state/app_state.dart';
import '../../services/image_loader.dart';
import '../sheet/function_sheet.dart';
import '../widgets.dart';

/// 调整面板：加载图像 + 亮度/对比度/高斯模糊 + 应用/恢复（对应桌面版基本调整卡）
class AdjustPanel extends ConsumerStatefulWidget {
  const AdjustPanel({super.key});
  @override
  ConsumerState<AdjustPanel> createState() => _AdjustPanelState();
}

class _AdjustPanelState extends ConsumerState<AdjustPanel> {
  double _brightness = 1.0, _contrast = 1.0, _blur = 1.0;

  Future<void> _load() async {
    // 让用户选来源：相册 / 文件
    final src = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('从相册选择'),
              onTap: () => Navigator.pop(ctx, 'gallery'),
            ),
            ListTile(
              leading: const Icon(Icons.folder_open_outlined),
              title: const Text('从文件选择'),
              subtitle: const Text('jpg / png / bmp / webp'),
              onTap: () => Navigator.pop(ctx, 'file'),
            ),
          ],
        ),
      ),
    );
    if (src == null) return;

    ref.read(statusMessageProvider.notifier).state = '正在选择图像…';
    final picked = src == 'gallery'
        ? await ImageLoader.pickFromGallery()
        : await ImageLoader.pickFromFile();
    if (picked == null) {
      ref.read(statusMessageProvider.notifier).state = '未选择图像或解码失败';
      return;
    }
    await ref.read(imageProvider.notifier).loadFromRgb(
          picked.rgb,
          picked.width,
          picked.height,
          name: picked.name,
        );
    // 加载后回到「原图」视图
    ref.read(viewModeProvider.notifier).state = CanvasViewMode.original;
  }

  Future<void> _apply() async {
    await ref.read(imageProvider.notifier).applyAdjust(
          brightness: _brightness,
          contrast: _contrast,
          blurKsize: _blur.round(),
        );
    // 应用后自动收起 sheet，立刻看到调整后的图像效果
    ref.read(sheetCollapseRequestProvider.notifier).state++;
  }

  void _restore() {
    ref.read(imageProvider.notifier).restoreSource();
    setState(() {
      _brightness = 1.0;
      _contrast = 1.0;
      _blur = 1.0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final hasImage = ref.watch(imageProvider.select((s) => s.hasImage));
    final busy = ref.watch(imageProvider.select((s) => s.busy));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const PanelTitle(icon: Icons.tune_rounded, title: '基本调整', sub: '每次「应用调整」叠加在当前图上，可连续迭代'),
        const SizedBox(height: 8),
        CandyButton(
          label: busy ? '处理中…' : '加载图像',
          icon: Icons.file_upload_outlined,
          onPressed: busy ? null : _load,
        ),
        SliderRow(label: '亮度', value: _brightness, min: 0.4, max: 1.8, onChanged: (v) => setState(() => _brightness = v)),
        SliderRow(label: '对比度', value: _contrast, min: 0.4, max: 1.8, onChanged: (v) => setState(() => _contrast = v)),
        SliderRow(label: '高斯模糊', value: _blur, min: 1, max: 15, decimals: 0, onChanged: (v) => setState(() => _blur = v)),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(
            child: CandyButton(
              label: '应用调整',
              primary: false,
              onPressed: (hasImage && !busy) ? _apply : null,
            ),
          ),
          const SizedBox(width: 9),
          Expanded(
            child: CandyButton(
              label: '恢复原图',
              primary: false,
              onPressed: (hasImage && !busy) ? _restore : null,
            ),
          ),
        ]),
      ],
    );
  }
}
