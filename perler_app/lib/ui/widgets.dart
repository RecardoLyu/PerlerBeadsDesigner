import 'package:flutter/material.dart';
import '../../theme/candy_theme.dart';

/// 糖果主按钮（紫罗兰渐变）/ 幽灵按钮
class CandyButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool primary;
  final bool expand;
  final bool compact; // 稍小尺寸（取消/应用等次级操作）
  const CandyButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.primary = true,
    this.expand = true,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final child = Container(
      height: compact ? 36 : 44,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: primary ? candyPrimaryGradient(context) : null,
        color: primary ? null : c.surface,
        border: primary ? null : Border.all(color: c.border),
        borderRadius: BorderRadius.circular(compact ? 12 : 16),
        boxShadow: primary
            ? [BoxShadow(color: c.violetDeep.withOpacity(0.35), blurRadius: 14, offset: const Offset(0, 4))]
            : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (icon != null) ...[
            Icon(icon, size: compact ? 14 : 16, color: primary ? Colors.white : Theme.of(context).colorScheme.primary),
            const SizedBox(width: 7),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: compact ? 12.5 : 13.5,
              fontWeight: FontWeight.w700,
              color: primary ? Colors.white : Theme.of(context).colorScheme.primary,
            ),
          ),
        ],
      ),
    );
    final tapped = GestureDetector(onTap: onPressed, child: child);
    return expand ? SizedBox(width: double.infinity, child: tapped) : tapped;
  }
}

/// 单选 chip 组
class CandyChips extends StatelessWidget {
  final List<String> options;
  final int selected;
  final ValueChanged<int> onChanged;
  const CandyChips({super.key, required this.options, required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: List.generate(options.length, (i) {
        final on = i == selected;
        return GestureDetector(
          onTap: () => onChanged(i),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 8),
            constraints: const BoxConstraints(minHeight: 36),
            decoration: BoxDecoration(
              gradient: on ? candyPrimaryGradient(context) : null,
              color: on ? null : c.muted,
              border: on ? null : Border.all(color: c.border),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              options[i],
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w700,
                color: on ? Colors.white : c.mutedFg,
              ),
            ),
          ),
        );
      }),
    );
  }
}

/// 标签 + 滑块 + 数值回显 一行
class SliderRow extends StatelessWidget {
  final String label;
  final double value, min, max;
  final int? decimals;
  final ValueChanged<double> onChanged;
  const SliderRow({
    super.key,
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    this.decimals = 2,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          SizedBox(width: 58, child: Text(label, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: c.mutedFg))),
          Expanded(
            child: Slider(value: value.clamp(min, max), min: min, max: max, onChanged: onChanged),
          ),
          Container(
            width: 52,
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
            decoration: BoxDecoration(
              color: c.surface,
              border: Border.all(color: c.mutedFg, style: BorderStyle.solid),
              borderRadius: BorderRadius.circular(9),
            ),
            child: Text(
              value.toStringAsFixed(decimals ?? 2),
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: c.foregroundStrong),
            ),
          ),
        ],
      ),
    );
  }
}

/// 标签 + 下拉 一行
/// 风格贴合糖果玻璃拟态：弹出菜单用 surfaceStrong 玻璃底 + 圆角 + 主题色描边，
/// 下拉箭头/文字用主题色，避免 Material 默认灰白弹窗与整体风格脱节。
/// 可选 [leading]：给每个选项在文字前画一个小示意（如分割形状/结构元素图形），
/// 与文字左对齐、垂直居中（替代塞进文字里的 Unicode 字符，渲染更精细、对齐更稳）。
class SelectRow<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<(T, String)> items;
  final ValueChanged<T> onChanged;
  /// 可选：按选项值返回前置示意小图标（约 18px），null 表示不画。
  final Widget? Function(T value)? leading;
  const SelectRow({
    super.key,
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
    this.leading,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final primary = Theme.of(context).colorScheme.primary;

    Widget itemChild(T v, String text) {
      final lead = leading?.call(v);
      return Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          if (lead != null) ...[
            SizedBox(width: 20, height: 20, child: Center(child: lead)),
            const SizedBox(width: 9),
          ],
          Text(text,
              style: TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600, color: c.foreground)),
        ],
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(width: 58, child: Text(label, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: c.mutedFg))),
          Expanded(
            child: DropdownButtonFormField<T>(
              value: value,
              isExpanded: true,
              // 弹出菜单：玻璃底 + 大圆角，贴合整体拟态风
              dropdownColor: c.surfaceStrong,
              borderRadius: BorderRadius.circular(16),
              elevation: 6,
              icon: Icon(Icons.keyboard_arrow_down_rounded, color: primary, size: 22),
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: c.foreground),
              decoration: const InputDecoration(),
              items: items
                  .map((e) => DropdownMenuItem(value: e.$1, child: itemChild(e.$1, e.$2)))
                  .toList(),
              onChanged: (v) => v != null ? onChanged(v) : null,
            ),
          ),
        ],
      ),
    );
  }
}

/// 复选行
class CheckRow extends StatelessWidget {
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;
  const CheckRow({super.key, required this.label, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => onChanged(!value),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            SizedBox(
              width: 22, height: 22,
              child: Checkbox(value: value, onChanged: (v) => onChanged(v ?? false)),
            ),
            const SizedBox(width: 9),
            Text(label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: context.candy.foreground)),
          ],
        ),
      ),
    );
  }
}

/// 面板小节标题
class PanelTitle extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? sub;
  const PanelTitle({super.key, required this.icon, required this.title, this.sub});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 15, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 7),
            Text(title, style: TextStyle(fontFamily: 'Fredoka', fontSize: 14, fontWeight: FontWeight.w600, color: c.foregroundStrong)),
          ]),
          if (sub != null)
            Padding(
              padding: const EdgeInsets.only(top: 2, left: 22),
              child: Text(sub!, style: TextStyle(fontSize: 11, color: c.mutedFg)),
            ),
        ],
      ),
    );
  }
}

class PanelDivider extends StatelessWidget {
  const PanelDivider({super.key});
  @override
  Widget build(BuildContext context) =>
      Container(height: 1, color: context.candy.border, margin: const EdgeInsets.symmetric(vertical: 14));
}

/// 手绘形状示意小图标：替代塞进文字里的 Unicode 字符（▭⬭●■┼◆…），
/// 用 CustomPainter 画出标准、统一线宽/圆角的图形，颜色跟主题色，渲染精细且对齐稳定。
/// 供 SelectRow.leading 使用（初始分割形状 / 形态学结构元素）。
enum ShapeGlyphKind {
  rect,      // 矩形（分割形状 / 矩形结构元素）
  ellipse,   // 椭圆
  freehand,  // 自由曲线
  cross,     // 十字
  vline,     // 垂直线
  hline,     // 水平线
  diamond,   // 菱形
}

class ShapeGlyph extends StatelessWidget {
  final ShapeGlyphKind kind;
  final double size;
  const ShapeGlyph(this.kind, {super.key, this.size = 18});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    return CustomPaint(
      size: Size.square(size),
      painter: _ShapeGlyphPainter(kind, color),
    );
  }
}

class _ShapeGlyphPainter extends CustomPainter {
  final ShapeGlyphKind kind;
  final Color color;
  const _ShapeGlyphPainter(this.kind, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final stroke = Paint()
      ..color = color
      ..strokeWidth = 1.7
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final w = size.width, h = size.height;
    final inset = w * 0.16;
    final rect = Rect.fromLTRB(inset, h * 0.28, w - inset, h * 0.72);

    switch (kind) {
      case ShapeGlyphKind.rect:
        canvas.drawRRect(
            RRect.fromRectAndRadius(rect, Radius.circular(w * 0.08)), stroke);
      case ShapeGlyphKind.ellipse:
        canvas.drawOval(rect, stroke);
      case ShapeGlyphKind.freehand:
        // 一条手绘感曲线（三段二次贝塞尔）
        final p = Path()
          ..moveTo(w * 0.14, h * 0.68)
          ..quadraticBezierTo(w * 0.22, h * 0.28, w * 0.42, h * 0.44)
          ..quadraticBezierTo(w * 0.58, h * 0.58, w * 0.66, h * 0.36)
          ..quadraticBezierTo(w * 0.74, h * 0.18, w * 0.88, h * 0.30);
        canvas.drawPath(p, stroke);
        // 起笔小点
        canvas.drawCircle(Offset(w * 0.14, h * 0.68), w * 0.05,
            Paint()..color = color);
      case ShapeGlyphKind.cross:
        final cx = w / 2, cy = h / 2, arm = w * 0.26;
        final p = Path()
          ..moveTo(cx, cy - arm)..lineTo(cx, cy + arm)
          ..moveTo(cx - arm, cy)..lineTo(cx + arm, cy);
        canvas.drawPath(p, stroke);
      case ShapeGlyphKind.vline:
        canvas.drawLine(Offset(w / 2, inset), Offset(w / 2, h - inset), stroke);
      case ShapeGlyphKind.hline:
        canvas.drawLine(Offset(inset, h / 2), Offset(w - inset, h / 2), stroke);
      case ShapeGlyphKind.diamond:
        final cx = w / 2, cy = h / 2, r = w * 0.30;
        final p = Path()
          ..moveTo(cx, cy - r)
          ..lineTo(cx + r, cy)
          ..lineTo(cx, cy + r)
          ..lineTo(cx - r, cy)
          ..close();
        canvas.drawPath(p, stroke);
    }
  }

  @override
  bool shouldRepaint(_ShapeGlyphPainter old) => old.kind != kind || old.color != color;
}

