import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../theme/candy_theme.dart';

/// 图纸画板首次使用引导：四页静态手势图解，不依赖网络或额外图片资源。
class BoardGuideDialog extends StatefulWidget {
  const BoardGuideDialog({super.key});

  static const seenKey = 'board_guide_seen_v1';

  static Future<void> showIfFirstUse(BuildContext context) async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(seenKey) == true || !context.mounted) return;
    await showDialog<void>(
      context: context,
      builder: (_) => const BoardGuideDialog(),
    );
    await prefs.setBool(seenKey, true);
  }

  @override
  State<BoardGuideDialog> createState() => _BoardGuideDialogState();
}

class _BoardGuideDialogState extends State<BoardGuideDialog> {
  final _controller = PageController();
  int _page = 0;

  static const _pages = [
    (
      Icons.add_photo_alternate_outlined,
      '上传与更换底图',
      '展开底部「图纸画板」面板，在「参考底图」中点「上传底图」。已有底图时，点「更换底图…」即可换一张。',
      '手指操作：单指点按钮；选择相册图片。',
    ),
    (
      Icons.open_with_rounded,
      '调透明度与底图位置',
      '拖动「不透明度」滑块改变底图深浅。点「调整底图」后，单指拖动平移、双指捏合缩放；最后点「保存调整」，点「取消」则还原。',
      '手指操作：滑块用单指拖动；底图用单指平移、双指缩放。',
    ),
    (
      Icons.gesture_rounded,
      '绘制、换色与撤销',
      '单指在画板上涂抹；双指捏合、拖动可缩放和平移画板。点工具换画笔／橡皮／填充／框选，拖「笔触粗细」换笔触，点圆形色块换颜色；画错点撤销，也可重做。',
      '手指操作：绘制和选色都用单指；双指只调整视野。',
    ),
    (
      Icons.file_download_outlined,
      '导出图纸',
      '在「导出图纸」中选择真实风／图纸风、文件名与分辨率，再点「导出 PNG 到相册」。成品保存在 Pictures/拼豆图纸，BOM 会显示在画板面板底部。',
      '手指操作：逐项单指选择，最后点导出按钮。',
    ),
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final last = _page == _pages.length - 1;
    return Dialog(
      backgroundColor: c.surfaceStrong,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 430, maxHeight: 590),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(children: [
                Expanded(
                  child: Text('图纸画板 · 新手引导',
                      style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: c.foregroundStrong)),
                ),
                IconButton(
                  tooltip: '关闭引导',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close_rounded),
                ),
              ]),
              Flexible(
                child: PageView.builder(
                  controller: _controller,
                  itemCount: _pages.length,
                  onPageChanged: (i) => setState(() => _page = i),
                  itemBuilder: (_, i) {
                    final p = _pages[i];
                    return SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Column(children: [
                        Container(
                          width: 88,
                          height: 88,
                          decoration: BoxDecoration(
                            gradient: candyPrimaryGradient(context),
                            borderRadius: BorderRadius.circular(28),
                          ),
                          child: Icon(p.$1, size: 44, color: Colors.white),
                        ),
                        const SizedBox(height: 18),
                        Text(p.$2,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.w700,
                                color: c.foregroundStrong)),
                        const SizedBox(height: 12),
                        Text(p.$3,
                            style: TextStyle(
                                fontSize: 14,
                                height: 1.65,
                                color: c.foreground)),
                        const SizedBox(height: 14),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                              color: c.muted,
                              borderRadius: BorderRadius.circular(14)),
                          child: Text(p.$4,
                              style: TextStyle(
                                  fontSize: 12.5,
                                  height: 1.5,
                                  color: c.mutedFg)),
                        ),
                      ]),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                    _pages.length,
                    (i) => AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          width: i == _page ? 20 : 7,
                          height: 7,
                          margin: const EdgeInsets.symmetric(horizontal: 3),
                          decoration: BoxDecoration(
                            color: i == _page
                                ? Theme.of(context).colorScheme.primary
                                : c.border,
                            borderRadius: BorderRadius.circular(99),
                          ),
                        )),
              ),
              const SizedBox(height: 14),
              Row(children: [
                if (_page > 0)
                  TextButton(
                    onPressed: () => _controller.previousPage(
                        duration: const Duration(milliseconds: 220),
                        curve: Curves.easeOut),
                    child: const Text('上一步'),
                  )
                else
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('跳过')),
                const Spacer(),
                FilledButton(
                  onPressed: () {
                    if (last) {
                      Navigator.pop(context);
                    } else {
                      _controller.nextPage(
                          duration: const Duration(milliseconds: 220),
                          curve: Curves.easeOut);
                    }
                  },
                  child: Text(last ? '开始绘制' : '下一步'),
                ),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}
