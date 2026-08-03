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
  // 裁剪态派生自 interactionProvider（切 Tab/进其它交互会自动取消裁剪 → 按钮自动还原）

  void _enterCrop() {
    cancelCanvasInteraction(ref); // 进裁剪前先取消框选/涂抹等子交互
    ref.read(interactionRequestProvider.notifier).state = CanvasInteraction.crop;
    ref.read(interactionProvider.notifier).state = CanvasInteraction.crop;
    ref.read(statusMessageProvider.notifier).state = '在图上框选要保留的区域，可拖动边框微调';
    // 收起 sheet 露出画布便于框选
    ref.read(sheetCollapseRequestProvider.notifier).state++;
  }

  void _cancelCrop() {
    cancelCanvasInteraction(ref);
    ref.read(statusMessageProvider.notifier).state = '已取消裁剪';
  }

  Future<void> _applyCrop() async {
    final rect = ref.read(cropRectProvider);
    if (rect == null || rect.width < 2 || rect.height < 2) {
      ref.read(statusMessageProvider.notifier).state = '请先在图上框选要保留的区域';
      return;
    }
    await ref.read(imageProvider.notifier).applyCrop(rect);
    cancelCanvasInteraction(ref);
  }

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
    // 裁剪态跟随全局交互：切 Tab/进其它交互取消裁剪后按钮自动还原「裁剪」
    final cropping = ref.watch(interactionProvider) == CanvasInteraction.crop;

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
        // 裁剪：默认单个「裁剪」按钮；进入裁剪模式后换成「取消/应用」两个较小按钮
        if (!cropping)
          CandyButton(
            label: '裁剪',
            icon: Icons.crop_rounded,
            primary: false,
            onPressed: (hasImage && !busy) ? _enterCrop : null,
          )
        else
          Row(children: [
            Expanded(
              child: CandyButton(
                label: '取消',
                primary: false,
                compact: true,
                onPressed: _cancelCrop,
              ),
            ),
            const SizedBox(width: 9),
            Expanded(
              child: CandyButton(
                label: '应用',
                primary: true,
                compact: true,
                onPressed: busy ? null : _applyCrop,
              ),
            ),
          ]),
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
