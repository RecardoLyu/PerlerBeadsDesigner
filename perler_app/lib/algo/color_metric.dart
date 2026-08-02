import 'dart:math';

/// CIE 色差度量。与桌面版 src/core/color_manager.py 的实现对拍，保证两端结果一致。
class Lab {
  final double l, a, b;
  const Lab(this.l, this.a, this.b);
}

class ColorMetric {
  ColorMetric._();

  /// sRGB(0-255) -> CIE Lab（D65）。逐行对应 Python 版 rgb_to_lab。
  static Lab rgbToLab(int r, int g, int b) {
    // sRGB -> linear
    double lin(int c) {
      final v = c / 255.0;
      return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4).toDouble();
    }

    final rl = lin(r), gl = lin(g), bl = lin(b);
    // linear RGB -> XYZ (D65)
    final x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047;
    final y = (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) / 1.00000;
    final z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883;

    double f(double t) =>
        t > 0.008856 ? pow(t, 1 / 3).toDouble() : (7.787 * t) + 16 / 116;

    final fx = f(x), fy = f(y), fz = f(z);
    return Lab(116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz));
  }

  /// CIE76：Lab 空间欧氏距离。
  static double ciede76(Lab x, Lab y) {
    final dl = x.l - y.l, da = x.a - y.a, db = x.b - y.b;
    return sqrt(dl * dl + da * da + db * db);
  }

  /// CIEDE2000。标准实现（Sharma et al.），与 Python 版逐行一致。
  static double ciede2000(Lab x, Lab y, {double kL = 1, double kC = 1, double kH = 1}) {
    final l1 = x.l, a1 = x.a, b1 = x.b;
    final l2 = y.l, a2 = y.a, b2 = y.b;

    final c1 = sqrt(a1 * a1 + b1 * b1);
    final c2 = sqrt(a2 * a2 + b2 * b2);
    final cBar = (c1 + c2) / 2;
    final cBar7 = pow(cBar, 7).toDouble();
    final g = 0.5 * (1 - sqrt(cBar7 / (cBar7 + pow(25, 7).toDouble())));

    final a1p = a1 * (1 + g);
    final a2p = a2 * (1 + g);
    final c1p = sqrt(a1p * a1p + b1 * b1);
    final c2p = sqrt(a2p * a2p + b2 * b2);

    double hp(double ap, double bb) {
      if (ap == 0 && bb == 0) return 0;
      var h = atan2(bb, ap) * 180 / pi;
      if (h < 0) h += 360;
      return h;
    }

    final h1p = hp(a1p, b1);
    final h2p = hp(a2p, b2);

    final dLp = l2 - l1;
    final dCp = c2p - c1p;
    double dhp;
    if (c1p * c2p == 0) {
      dhp = 0;
    } else if ((h2p - h1p).abs() <= 180) {
      dhp = h2p - h1p;
    } else if (h2p - h1p > 180) {
      dhp = h2p - h1p - 360;
    } else {
      dhp = h2p - h1p + 360;
    }
    final dHp = 2 * sqrt(c1p * c2p) * sin(dhp * pi / 360);

    final lBarP = (l1 + l2) / 2;
    final cBarP = (c1p + c2p) / 2;
    double hBarP;
    if (c1p * c2p == 0) {
      hBarP = h1p + h2p;
    } else if ((h1p - h2p).abs() <= 180) {
      hBarP = (h1p + h2p) / 2;
    } else if (h1p + h2p < 360) {
      hBarP = (h1p + h2p + 360) / 2;
    } else {
      hBarP = (h1p + h2p - 360) / 2;
    }

    final t = 1 -
        0.17 * cos((hBarP - 30) * pi / 180) +
        0.24 * cos(2 * hBarP * pi / 180) +
        0.32 * cos((3 * hBarP + 6) * pi / 180) -
        0.20 * cos((4 * hBarP - 63) * pi / 180);

    final dTheta = 30 * exp(-pow((hBarP - 275) / 25, 2).toDouble());
    final cBarP7 = pow(cBarP, 7).toDouble();
    final rC = 2 * sqrt(cBarP7 / (cBarP7 + pow(25, 7).toDouble()));
    final sL = 1 + (0.015 * pow(lBarP - 50, 2).toDouble()) / sqrt(20 + pow(lBarP - 50, 2).toDouble());
    final sC = 1 + 0.045 * cBarP;
    final sH = 1 + 0.015 * cBarP * t;
    final rT = -sin(2 * dTheta * pi / 180) * rC;

    final dl = dLp / (kL * sL);
    final dc = dCp / (kC * sC);
    final dh = dHp / (kH * sH);
    return sqrt(dl * dl + dc * dc + dh * dh + rT * dc * dh);
  }

  /// 加权 RGB 距离（人眼对 RGB 敏感度加权）。
  static double weighted(int r1, int g1, int b1, int r2, int g2, int b2) {
    final dr = (r1 - r2).toDouble(), dg = (g1 - g2).toDouble(), db = (b1 - b2).toDouble();
    return sqrt(0.30 * dr * dr + 0.59 * dg * dg + 0.11 * db * db);
  }
}
