import 'package:flutter/material.dart';

import 'skin.dart';

/// 拼豆图纸生成器 · 糖果系玻璃拟态设计 token
/// 直接翻译自 design/mobile/android_prototype.html 的 CSS 变量，保证与桌面版/原型风格一致。
class CandyColors {
  CandyColors._();

  // ---- 亮色主题 token（:root）----
  static const Color primaryLight = Color(0xFFE11D48);
  static const Color onPrimaryLight = Color(0xFFFFFFFF);
  static const Color secondaryLight = Color(0xFFFB7185);
  static const Color accentLight = Color(0xFF2563EB);
  static const Color onAccentLight = Color(0xFFFFFFFF);
  static const Color violetLight = Color(0xFFA78BFA);
  static const Color violetDeepLight = Color(0xFF7C3AED);
  static const Color bgLight = Color(0xFFFFF1F2);
  static const Color bg2Light = Color(0xFFFFE4E6);
  static const Color surfaceLight = Color(0x8CFFFFFF); // rgba(255,255,255,.55)
  static const Color surfaceStrongLight = Color(0xBFFFFFFF); // rgba(255,255,255,.75)
  static const Color foregroundLight = Color(0xFF4A1428);
  static const Color foregroundStrongLight = Color(0xFF881337);
  static const Color mutedLight = Color(0xFFF0ECF2);
  static const Color mutedFgLight = Color(0xFF9A6B7C);
  static const Color borderLight = Color(0x2EE11D48); // rgba(225,29,72,.18)
  static const Color destructiveLight = Color(0xFFDC2626);

  // ---- 暗色主题 token（[data-theme="dark"]）----
  static const Color primaryDark = Color(0xFFFB7185);
  static const Color onPrimaryDark = Color(0xFF2A0A12);
  static const Color secondaryDark = Color(0xFFFDA4AF);
  static const Color accentDark = Color(0xFF60A5FA);
  static const Color onAccentDark = Color(0xFF0B1220);
  static const Color violetDark = Color(0xFFC4B5FD);
  static const Color violetDeepDark = Color(0xFFA78BFA);
  static const Color bgDark = Color(0xFF1A0F14);
  static const Color bg2Dark = Color(0xFF241019);
  static const Color surfaceDark = Color(0xD1261218); // rgba(38,18,24,.82)：加浓，浅色图透上来时叠层文字/图标仍清晰
  static const Color surfaceStrongDark = Color(0xE63A1C28); // rgba(58,28,40,.9)：更不透明，保证对比度
  static const Color foregroundDark = Color(0xFFF6E4EA);
  static const Color foregroundStrongDark = Color(0xFFFBD5DE);
  static const Color mutedDark = Color(0xFF2E1620);
  static const Color mutedFgDark = Color(0xFFD9B3C0); // 提亮，暗玻璃上更耐读
  static const Color borderDark = Color(0x38FB7185); // rgba(251,113,133,.22)
  static const Color destructiveDark = Color(0xFFF87171);
}

/// 玻璃模糊半径（与 CSS --glass-blur:18px 对应）
const double kGlassBlur = 18.0;

/// 主题相关的渐变色对（主按钮 / 选中态用）。
/// 读当前 CandyTheme 扩展的 violet/violetDeep —— 换肤后自动跟随皮肤色。
LinearGradient candyPrimaryGradient(BuildContext context) {
  final c = context.candy;
  return LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [c.violet, c.violetDeep],
  );
}

/// 整体 ThemeData 构建。[skin] 非空时按皮肤色覆盖主色/渐变对/背景染色，
/// 且 scaffold 背景透明（壁纸由 MaterialApp.builder 的 SkinBackdrop 提供）。
ThemeData buildCandyTheme(Brightness brightness, {SkinPalette? skin}) {
  final light = brightness == Brightness.light;
  final primary = skin?.primary ?? (light ? CandyColors.primaryLight : CandyColors.primaryDark);
  final onPrimary = skin?.onPrimary ?? (light ? CandyColors.onPrimaryLight : CandyColors.onPrimaryDark);
  final bg = skin?.bg ?? (light ? CandyColors.bgLight : CandyColors.bgDark);
  final bg2 = skin?.bg2 ?? (light ? CandyColors.bg2Light : CandyColors.bg2Dark);
  final surface = skin?.surface ?? (light ? CandyColors.surfaceLight : CandyColors.surfaceDark);
  final surfaceStrong = skin?.surfaceStrong ??
      (light ? CandyColors.surfaceStrongLight : CandyColors.surfaceStrongDark);
  final foreground =
      light ? CandyColors.foregroundLight : CandyColors.foregroundDark;
  final foregroundStrong = light
      ? CandyColors.foregroundStrongLight
      : CandyColors.foregroundStrongDark;
  final muted = light ? CandyColors.mutedLight : CandyColors.mutedDark;
  final mutedFg = light ? CandyColors.mutedFgLight : CandyColors.mutedFgDark;
  final border = skin?.border ?? (light ? CandyColors.borderLight : CandyColors.borderDark);
  final violet = skin?.violet ?? (light ? CandyColors.violetLight : CandyColors.violetDark);
  final violetDeep = skin?.violetDeep ??
      (light ? CandyColors.violetDeepLight : CandyColors.violetDeepDark);

  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    fontFamily: 'Nunito',
  );

  return base.copyWith(
    scaffoldBackgroundColor: skin != null ? Colors.transparent : bg,
    colorScheme: base.colorScheme.copyWith(
      primary: primary,
      onPrimary: onPrimary,
      secondary: violet,
      surface: surface,
      onSurface: foreground,
      outline: border,
    ),
    // 供自定义控件读取的扩展 token
    extensions: [
      CandyTheme(
        bg: bg,
        bg2: bg2,
        surface: surface,
        surfaceStrong: surfaceStrong,
        foreground: foreground,
        foregroundStrong: foregroundStrong,
        muted: muted,
        mutedFg: mutedFg,
        border: border,
        violet: violet,
        violetDeep: violetDeep,
      ),
    ],
    sliderTheme: base.sliderTheme.copyWith(
      activeTrackColor: primary,
      thumbColor: Colors.white,
      overlayColor: primary.withOpacity(0.15),
      inactiveTrackColor: muted,
      thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 11),
      trackHeight: 7,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surfaceStrong,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(13),
        borderSide: BorderSide(color: border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(13),
        borderSide: BorderSide(color: border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(13),
        borderSide: BorderSide(color: primary, width: 2),
      ),
    ),
  );
}

/// 通过 ThemeExtension 暴露糖果 token，任意控件 Theme.of(context).candy 取用。
class CandyTheme extends ThemeExtension<CandyTheme> {
  final Color bg, bg2, surface, surfaceStrong;
  final Color foreground, foregroundStrong;
  final Color muted, mutedFg, border, violet, violetDeep;

  const CandyTheme({
    required this.bg,
    required this.bg2,
    required this.surface,
    required this.surfaceStrong,
    required this.foreground,
    required this.foregroundStrong,
    required this.muted,
    required this.mutedFg,
    required this.border,
    required this.violet,
    required this.violetDeep,
  });

  @override
  CandyTheme copyWith({
    Color? bg, bg2, surface, surfaceStrong,
    Color? foreground, foregroundStrong,
    Color? muted, mutedFg, border, violet, violetDeep,
  }) =>
      CandyTheme(
        bg: bg ?? this.bg,
        bg2: bg2 ?? this.bg2,
        surface: surface ?? this.surface,
        surfaceStrong: surfaceStrong ?? this.surfaceStrong,
        foreground: foreground ?? this.foreground,
        foregroundStrong: foregroundStrong ?? this.foregroundStrong,
        muted: muted ?? this.muted,
        mutedFg: mutedFg ?? this.mutedFg,
        border: border ?? this.border,
        violet: violet ?? this.violet,
        violetDeep: violetDeep ?? this.violetDeep,
      );

  @override
  CandyTheme lerp(ThemeExtension<CandyTheme>? other, double t) {
    if (other is! CandyTheme) return this;
    Color c(Color a, Color b) => Color.lerp(a, b, t)!;
    return CandyTheme(
      bg: c(bg, other.bg),
      bg2: c(bg2, other.bg2),
      surface: c(surface, other.surface),
      surfaceStrong: c(surfaceStrong, other.surfaceStrong),
      foreground: c(foreground, other.foreground),
      foregroundStrong: c(foregroundStrong, other.foregroundStrong),
      muted: c(muted, other.muted),
      mutedFg: c(mutedFg, other.mutedFg),
      border: c(border, other.border),
      violet: c(violet, other.violet),
      violetDeep: c(violetDeep, other.violetDeep),
    );
  }
}

extension CandyX on BuildContext {
  CandyTheme get candy => Theme.of(this).extension<CandyTheme>()!;
}
