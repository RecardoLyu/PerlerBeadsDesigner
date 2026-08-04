import 'package:flutter/material.dart';
import '../widgets.dart';
import 'adjust_panel.dart';
import 'segment_panel.dart';

/// 图像调整面板：整合「调整 + 分割」，顶部子分段切换。
/// 两个子面板均保持原有功能不变（迁移自原独立 Tab）。
class ImageAdjustPanel extends StatefulWidget {
  const ImageAdjustPanel({super.key});
  @override
  State<ImageAdjustPanel> createState() => _ImageAdjustPanelState();
}

class _ImageAdjustPanelState extends State<ImageAdjustPanel> {
  int _sub = 0; // 0=调整 1=分割

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CandySegment(
          options: const ['调整', '分割'],
          selected: _sub,
          onChanged: (i) => setState(() => _sub = i),
        ),
        const SizedBox(height: 10),
        _sub == 0 ? const AdjustPanel() : const SegmentPanel(),
      ],
    );
  }
}
