import 'dart:io' show File;
import 'dart:typed_data';
import 'dart:ui' show ImageFilter;
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;

import '../algo/pattern_render.dart';
import 'candy_theme.dart';

/// 图片换肤：与桌面端 src/webapp/skin.py + skin.js 同一套规则。
/// - extractDominantColors：降采样 64 → k=4 kmeans（k-means++ 播种）→
///   剔除近白/近黑/灰 → score=簇像素数×饱和度降序取前 kSkinMaxColors 个；
///   无彩色返回空表（只换背景不换色）。
/// - deriveSkinPalette：主色定主题，辅助色调和面板；色相不变、夹取饱和/明度。
/// - prepareSkinBytes：导入时一次性预处理（≤1440 + JPEG 存无模糊缩放图），
///   运行时按模糊档用 ImageFiltered 实时模糊。

// ---- 与桌面端一致的常量 ----
const int kSkinSample = 64;
const int kSkinK = 4;
const int kSkinMaxColors = 3;
const double kLWhite = 0.95, kLBlack = 0.08, kSGray = 0.18;
const int kSkinWallpaperMaxSide = 1440;
const int kSkinJpegQuality = 88;
// 模糊三档（0=无，1=中，2=高）对应的 sigma
const List<double> kSkinBlurSigma = [0, 4, 9];


/// 0-255 RGB → [h 0-360, s 0-1, l 0-1]
List<double> rgbToHsl(int r, int g, int b) {
  final rr = r / 255.0, gg = g / 255.0, bb = b / 255.0;
  final mx = rr > gg ? (rr > bb ? rr : bb) : (gg > bb ? gg : bb);
  final mn = rr < gg ? (rr < bb ? rr : bb) : (gg < bb ? gg : bb);
  final l = (mx + mn) / 2.0;
  if (mx == mn) return [0, 0, l];
  final d = mx - mn;
  final s = l > 0.5 ? d / (2.0 - mx - mn) : d / (mx + mn);
  double h;
  if (mx == rr) {
    h = (gg - bb) / d + (gg < bb ? 6.0 : 0.0);
  } else if (mx == gg) {
    h = (bb - rr) / d + 2.0;
  } else {
    h = (rr - gg) / d + 4.0;
  }
  return [h * 60.0, s, l];
}

/// h(0-360)/s/l(0-1) → [r,g,b] 0-255
List<int> hslToRgb(double h, double s, double l) {
  h = ((h % 360) + 360) % 360 / 360.0;
  if (s == 0) {
    final v = (l * 255).round();
    return [v, v, v];
  }
  final q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  final p = 2 * l - q;
  double f(double t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  }
  return [
    (f(h + 1 / 3) * 255).round(),
    (f(h) * 255).round(),
    (f(h - 1 / 3) * 255).round(),
  ];
}

double _clampD(double v, double a, double b) => v < a ? a : (v > b ? b : v);

/// 提取主体颜色列表（score 降序，≤kSkinMaxColors 个 0xRRGGBB）；无彩色返回空表。
/// 用 k-means++ 播种（与桌面端 KMEANS_PP_CENTERS 同思路），对手动分桶播种在真实
/// 照片（色桶多）下越界崩溃的问题免疫；双端同输入同结果。
List<int> extractDominantColors(Uint8List rgb, int w, int h) {
  // 降采样到最长边 64（盒式平均 ≈ INTER_AREA）
  final scale = kSkinSample / (w > h ? w : h);
  final nw = w > h ? kSkinSample : (w * scale).round().clamp(1, kSkinSample);
  final nh = h >= w ? kSkinSample : (h * scale).round().clamp(1, kSkinSample);
  final small = PatternRender.boxAverageDownsample(rgb, w, h, nw, nh);
  final n = nw * nh;

  // k-means++ 播种：第一个取全局均值，之后按「距已选种子最小距离的平方」概率轮盘选
  final centers = <List<double>>[_meanPixel(small, n)];
  final dist2 = List<double>.filled(n, double.infinity);
  final rnd = _Lcg(0x5EED + n); // 定长伪随机（可复现，双端一致）
  while (centers.length < kSkinK) {
    final c = centers.last;
    var sum = 0.0;
    for (var i = 0; i < n; i++) {
      final d = _dist2px(small, i, c);
      if (d < dist2[i]) dist2[i] = d;
      sum += dist2[i];
    }
    if (sum <= 0) break; // 全同色
    var target = rnd.nextDouble() * sum;
    var pick = n - 1;
    for (var i = 0; i < n; i++) {
      target -= dist2[i];
      if (target <= 0) { pick = i; break; }
    }
    centers.add([small[pick * 3].toDouble(), small[pick * 3 + 1].toDouble(),
        small[pick * 3 + 2].toDouble()]);
  }

  // Lloyd 迭代
  final labels = Int32List(n);
  for (var iter = 0; iter < 20; iter++) {
    var moved = false;
    for (var i = 0; i < n; i++) {
      var best = 0, bestD = double.infinity;
      for (var k = 0; k < centers.length; k++) {
        final d = _dist2px(small, i, centers[k]);
        if (d < bestD) { bestD = d; best = k; }
      }
      if (labels[i] != best) { labels[i] = best; moved = true; }
    }
    final acc = List<List<double>>.generate(centers.length, (_) => [0, 0, 0, 0]);
    for (var i = 0; i < n; i++) {
      final a = acc[labels[i]];
      a[0] += small[i * 3];
      a[1] += small[i * 3 + 1];
      a[2] += small[i * 3 + 2];
      a[3] += 1;
    }
    for (var k = 0; k < centers.length; k++) {
      if (acc[k][3] > 0) {
        centers[k][0] = acc[k][0] / acc[k][3];
        centers[k][1] = acc[k][1] / acc[k][3];
        centers[k][2] = acc[k][2] / acc[k][3];
      }
    }
    if (!moved) break;
  }

  // 过滤 + score=count*饱和度，降序取前 kSkinMaxColors
  final scored = <_Scored>[];
  for (var k = 0; k < centers.length; k++) {
    var cnt = 0;
    for (var i = 0; i < n; i++) {
      if (labels[i] == k) cnt++;
    }
    if (cnt == 0) continue;
    final c = centers[k];
    final hsl = rgbToHsl(c[0].round(), c[1].round(), c[2].round());
    final s = hsl[1], l = hsl[2];
    if (l >= kLWhite || l <= kLBlack || s < kSGray) continue;
    scored.add(_Scored(cnt * s, c));
  }
  scored.sort((a, b) => b.score.compareTo(a.score));
  return [
    for (final e in scored.take(kSkinMaxColors))
      ((e.c[0].round().clamp(0, 255)) << 16) |
          ((e.c[1].round().clamp(0, 255)) << 8) |
          (e.c[2].round().clamp(0, 255)),
  ];
}

class _Scored {
  final double score;
  final List<double> c;
  _Scored(this.score, this.c);
}

List<double> _meanPixel(Uint8List px, int n) {
  double r = 0, g = 0, b = 0;
  for (var i = 0; i < n; i++) {
    r += px[i * 3];
    g += px[i * 3 + 1];
    b += px[i * 3 + 2];
  }
  return [r / n, g / n, b / n];
}

double _dist2px(Uint8List px, int i, List<double> c) {
  final dr = px[i * 3] - c[0], dg = px[i * 3 + 1] - c[1], db = px[i * 3 + 2] - c[2];
  return dr * dr + dg * dg + db * db;
}

/// 定长线性同余伪随机（k-means++ 轮盘用，保证可复现、双端一致）
class _Lcg {
  int _s;
  _Lcg(this._s);
  double nextDouble() {
    _s = (_s * 1103515245 + 12345) & 0x7FFFFFFF;
    return _s / 0x7FFFFFFF;
  }
}

/// 皮肤主题色推导结果（单个亮度下的一整套）
class SkinPalette {
  final Color primary, onPrimary, secondary;
  final Color violet, violetDeep, border;
  final Color bg, bg2; // 已带 alpha 的轻染色（页面渐变据此自动变薄）
  final Color surface, surfaceStrong;
  final Color shadow; // 卡片/按钮投影色（随主色派生，消灭硬编码紫红边）

  const SkinPalette({
    required this.primary,
    required this.onPrimary,
    required this.secondary,
    required this.violet,
    required this.violetDeep,
    required this.border,
    required this.bg,
    required this.bg2,
    required this.surface,
    required this.surfaceStrong,
    required this.shadow,
  });
}

Color _hslColor(double h, double s, double l, [double? a]) {
  final rgb = hslToRgb(h, _clampD(s, 0, 1), _clampD(l, 0, 1));
  return Color.fromARGB(a == null ? 255 : (a * 255).round(), rgb[0], rgb[1], rgb[2]);
}

/// 表面染色：以原表面色 RGB 为起点向主色 lerp，alpha 不动
Color _tintKeepAlpha(Color orig, Color p, double t) {
  final or = (orig.r * 255).round(), og = (orig.g * 255).round(), ob = (orig.b * 255).round();
  final pr = (p.r * 255).round(), pg = (p.g * 255).round(), pb = (p.b * 255).round();
  final r = (or + (pr - or) * t).round();
  final g = (og + (pg - og) * t).round();
  final b = (ob + (pb - ob) * t).round();
  return Color.fromARGB((orig.a * 255).round(), r, g, b);
}

/// 由主色（+可选辅助色）推导一整套皮肤色（与桌面端 skin.js derive 同规则）。
/// 辅助色用于调和面板/卡片玻璃底色与投影色，让多彩图的卡片不再单调偏红。
SkinPalette deriveSkinPalette(Color base, Brightness brightness, {Color? accent}) {
  final light = brightness == Brightness.light;
  final hsl = rgbToHsl(
      (base.r * 255).round(), (base.g * 255).round(), (base.b * 255).round());
  final h = hsl[0], s = hsl[1], l = hsl[2];
  double s2, l2;
  if (light) {
    s2 = _clampD(s, .45, .80);
    l2 = _clampD(l, .38, .50);
    if (l > .78) l2 = .45;
  } else {
    s2 = _clampD(s, .40, .75);
    l2 = _clampD(l, .60, .72);
  }
  final primary = _hslColor(h, s2, l2);
  final onPrimary = l2 <= .62 ? const Color(0xFFFFFFFF) : const Color(0xFF26131B);
  final secondary = _hslColor(h + 8, s2, _clampD(l2 + (light ? .18 : .12), 0, .8));
  final violet = _hslColor(h - 18, _clampD(s2, .45, .85), light ? .66 : .72);
  final violetDeep = _hslColor(h + 10, s2, light ? .52 : .60);
  final border = _hslColor(h, s2, l2, light ? .18 : .22);
  // bg/bg2：轻染色 + 带 alpha（页面 4 处渐变读扩展 bg/bg2，自动变薄露出壁纸）
  final bg = _hslColor(h, _clampD(s2 * .6, 0, .5), light ? .965 : .08, light ? .45 : .50);
  final bg2 = _hslColor(h, _clampD(s2 * .7, 0, .55), light ? .945 : .11, light ? .50 : .55);

  // 染色目标色：主色为主，有辅助色时向辅助色再调和一点（面板底色融入画面辅色）
  Color tintTarget = primary;
  if (accent != null) {
    tintTarget = _tintKeepAlpha(
        Color.fromARGB(255, (primary.r * 255).round(), (primary.g * 255).round(),
            (primary.b * 255).round()),
        accent, 0.30);
  }
  // surface 系：各端自家原值做 lerp 起点，alpha 不动
  final surfaceBase = light ? CandyColors.surfaceLight : CandyColors.surfaceDark;
  final surfaceStrongBase =
      light ? CandyColors.surfaceStrongLight : CandyColors.surfaceStrongDark;
  final t = light ? .08 : .12;
  // 投影色：主色（含辅色调和）的饱和版，供卡片/按钮 boxShadow 用
  final shadow = _hslColor(
      rgbToHsl((tintTarget.r * 255).round(), (tintTarget.g * 255).round(),
              (tintTarget.b * 255).round())[0],
      _clampD(s2, .4, .8), light ? .5 : .6, 1.0);
  return SkinPalette(
    primary: primary,
    onPrimary: onPrimary,
    secondary: secondary,
    violet: violet,
    violetDeep: violetDeep,
    border: border,
    bg: bg,
    bg2: bg2,
    surface: _tintKeepAlpha(surfaceBase, tintTarget, t),
    surfaceStrong: _tintKeepAlpha(surfaceStrongBase, tintTarget, t),
    shadow: shadow,
  );
}

/// 导入预处理结果（compute isolate 返回）
class SkinPrepareResult {
  final Uint8List wallpaper; // 已缩放、无模糊、JPEG 编码（运行时按档实时模糊）
  final List<int> colors;    // 0xRRGGBB 主+辅色列表（空=灰图等无彩色）
  const SkinPrepareResult(this.wallpaper, this.colors);
}

/// 导入时一次性预处理：解码→最长边 1440→取色→JPEG q88（存无模糊缩放图）。
/// 模糊在运行时按档位用 ImageFiltered 实时叠加，切档无需重新导入。
/// 顶层函数，供 compute() 在 isolate 中运行。
SkinPrepareResult prepareSkinBytes(Uint8List input) {
  final decoded = img.decodeImage(input);
  if (decoded == null) throw ArgumentError('无法解码图片');
  // 缩到最长边 ≤1440
  var work = decoded;
  final maxSide = decoded.width > decoded.height ? decoded.width : decoded.height;
  if (maxSide > kSkinWallpaperMaxSide) {
    final scale = kSkinWallpaperMaxSide / maxSide;
    work = img.copyResize(
      decoded,
      width: (decoded.width * scale).round().clamp(1, 1 << 20),
      height: (decoded.height * scale).round().clamp(1, 1 << 20),
      interpolation: img.Interpolation.average,
    );
  }
  // 取色（清晰像素）：转 RGB 字节 → 复用提取算法
  final rgbBytes = work.getBytes(order: img.ChannelOrder.rgb);
  final colors = extractDominantColors(rgbBytes, work.width, work.height);
  // 壁纸存无模糊缩放图（运行时按档模糊）
  final wallpaper = Uint8List.fromList(img.encodeJpg(work, quality: kSkinJpegQuality));
  return SkinPrepareResult(wallpaper, colors);
}

/// MaterialApp.builder 用的壁纸层：实色打底 → 半透明壁纸（按档实时模糊）→ 页面。
/// 页面渐变经 CandyTheme.bg/bg2（带 alpha）自动变薄，壁纸透出来。
class SkinBackdrop extends StatelessWidget {
  final bool enabled;
  final String? wallpaperPath;
  final double opacity;
  final int blurLevel; // 0=无，1=中，2=高
  final int version;   // 导入版本号：内容变化时强制重建 image provider
  final Widget child;

  const SkinBackdrop({
    super.key,
    required this.enabled,
    required this.wallpaperPath,
    required this.opacity,
    this.blurLevel = 1,
    this.version = 0,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    final path = wallpaperPath;
    if (!enabled || path == null || path.isEmpty) return child;
    final dark = Theme.of(context).brightness == Brightness.dark;
    // 路径恒定（skin_wallpaper.jpg），多次导入用自增 version 作 key 强制刷新，
    // 比 mtime（秒级、同秒可能不变）更可靠。
    final sigma = kSkinBlurSigma[blurLevel.clamp(0, kSkinBlurSigma.length - 1)];
    Widget image = Image.file(
      File(path),
      key: ValueKey('$path@v$version'),
      fit: BoxFit.cover,
      opacity: AlwaysStoppedAnimation(opacity),
    );
    if (sigma > 0) {
      image = ImageFiltered(
        imageFilter: ImageFilter.blur(sigmaX: sigma, sigmaY: sigma),
        child: image,
      );
    }
    return Stack(
      fit: StackFit.expand,
      children: [
        // 不透明实色打底（取原始常量：扩展里的 bg 已半透明）
        Container(color: dark ? CandyColors.bgDark : CandyColors.bgLight),
        Positioned.fill(child: image),
        child,
      ],
    );
  }
}
