import 'package:flutter/material.dart';
import '../../theme/candy_theme.dart';

/// 糖果主按钮（紫罗兰渐变）/ 幽灵按钮
class CandyButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool primary;
  final bool expand;
  const CandyButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.primary = true,
    this.expand = true,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    final child = Container(
      height: 44,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: primary ? candyPrimaryGradient(Theme.of(context).brightness) : null,
        color: primary ? null : c.surface,
        border: primary ? null : Border.all(color: c.border),
        borderRadius: BorderRadius.circular(16),
        boxShadow: primary
            ? [BoxShadow(color: c.violetDeep.withOpacity(0.35), blurRadius: 14, offset: const Offset(0, 4))]
            : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 16, color: primary ? Colors.white : Theme.of(context).colorScheme.primary),
            const SizedBox(width: 7),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: 13.5,
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
              gradient: on ? candyPrimaryGradient(Theme.of(context).brightness) : null,
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
class SelectRow<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<(T, String)> items;
  final ValueChanged<T> onChanged;
  const SelectRow({super.key, required this.label, required this.value, required this.items, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(width: 58, child: Text(label, style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: c.mutedFg))),
          Expanded(
            child: DropdownButtonFormField<T>(
              value: value,
              isExpanded: true,
              decoration: const InputDecoration(),
              items: items.map((e) => DropdownMenuItem(value: e.$1, child: Text(e.$2, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)))).toList(),
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
