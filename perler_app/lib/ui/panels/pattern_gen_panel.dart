import 'package:flutter/material.dart';
import '../widgets.dart';
import 'pattern_panel.dart';
import 'export_panel.dart';

/// 图纸生成面板：整合「图纸 + 导出」，顶部子分段切换。
/// 两个子面板均保持原有功能不变（迁移自原独立 Tab）。
class PatternGenPanel extends StatefulWidget {
  const PatternGenPanel({super.key});
  @override
  State<PatternGenPanel> createState() => _PatternGenPanelState();
}

class _PatternGenPanelState extends State<PatternGenPanel> {
  int _sub = 0; // 0=图纸 1=导出

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CandySegment(
          options: const ['图纸', '导出'],
          selected: _sub,
          onChanged: (i) => setState(() => _sub = i),
        ),
        const SizedBox(height: 10),
        _sub == 0 ? const PatternPanel() : const ExportPanel(),
      ],
    );
  }
}
