import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/services.dart' show rootBundle;
import 'color_metric.dart';

/// 拼豆颜色（对应桌面版 Color）
class BeadColor {
  final String code, name, hex;
  final int r, g, b;
  final Lab lab; // 标准 LAB（L 0-100, a/b -128~127）
  BeadColor(this.code, this.name, this.hex)
      : r = int.parse(hex.substring(1, 3), radix: 16),
        g = int.parse(hex.substring(3, 5), radix: 16),
        b = int.parse(hex.substring(5, 7), radix: 16),
        lab = ColorMetric.rgbToLab(
          int.parse(hex.substring(1, 3), radix: 16),
          int.parse(hex.substring(3, 5), radix: 16),
          int.parse(hex.substring(5, 7), radix: 16),
        );
}

/// 调色板 + 量化器（对应桌面版 ColorPalette + ColorManager.quantize_image）。
/// 与 Python 版逐行对拍：同样的色度保持、显著性加权、贪心 K-center、ICM、抖动。
class Palette {
  final List<BeadColor> colors;
  String metric;
  Palette(this.colors, {this.metric = 'ciede2000'});

  static Future<Palette> loadMard221() async {
    final s = await rootBundle.loadString('assets/palette/colors_221.json');
    final data = jsonDecode(s) as List;
    return Palette(data.map((d) => BeadColor(d['code'], d['name'], d['hex'])).toList());
  }

  // ---- 距离（对应 Color.distance_to）----
  double _dist(BeadColor c, int r, int g, int b, String metric) {
    switch (metric) {
      case 'euclidean':
        final dr = (c.r - r).toDouble(), dg = (c.g - g).toDouble(), db = (c.b - b).toDouble();
        return sqrt(dr * dr + dg * dg + db * db);
      case 'lab':
      case 'ciede76':
        return ColorMetric.ciede76(c.lab, ColorMetric.rgbToLab(r, g, b));
      case 'ciede2000':
        return ColorMetric.ciede2000(c.lab, ColorMetric.rgbToLab(r, g, b));
      case 'weighted':
      default:
        final dr = (c.r - r) / 255.0, dg = (c.g - g) / 255.0, db = (c.b - b) / 255.0;
        return sqrt(3 * dr * dr + 6 * dg * dg + 1 * db * db) * 255;
    }
  }

  /// 单像素最近色索引
  int closestIndex(int r, int g, int b) {
    var best = 0;
    var bestD = _dist(colors[0], r, g, b, metric);
    for (var i = 1; i < colors.length; i++) {
      final d = _dist(colors[i], r, g, b, metric);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    return best;
  }

  /// 批量最近色索引（无限制量化路径；对应 get_closest_indices_batch）
  Int32List closestIndicesBatch(Uint8List pixels, int n) {
    final out = Int32List(n);
    for (var i = 0; i < n; i++) {
      out[i] = closestIndex(pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2]);
    }
    return out;
  }
}

/// 量化结果
class QuantizeResult {
  final Uint8List rgb; // h*w*3 量化后 RGB
  final Map<String, int> usage; // code -> count
  QuantizeResult(this.rgb, this.usage);
}

/// 量化器（对应 ColorManager.quantize_image 及其辅助）。
class Quantizer {
  final Palette palette;
  Quantizer(this.palette);

  // 色度保持调参（与 Python 一致）
  static const double _CHROMA_SAT_MIN = 30.0;
  static const double _CHROMA_MATCH_TOL = 12.0;
  static const double _CHROMA_ALLOW_BOOST = 15.0;
  static const double _CHROMA_SOFT_PENALTY = 0.6;

  /// 主入口：把 h*w*3 RGB 量化为调色板颜色。
  /// [colorLimit] null/0 = 不限；[salience] 0-2；[dither] 是否误差扩散；
  /// [ditherStrength] 0-1；[icmSmooth] 0=关。
  QuantizeResult quantize(
    Uint8List img, int h, int w, {
    int? colorLimit,
    double salience = 1.0,
    bool dither = false,
    double ditherStrength = 1.0,
    double icmSmooth = 0.0,
  }) {
    final n = h * w;
    final metric = palette.metric;
    final P = palette.colors.length;

    // 统计唯一颜色数
    final uniq = <int>{};
    for (var i = 0; i < n; i++) {
      uniq.add((img[i * 3] << 16) | (img[i * 3 + 1] << 8) | img[i * 3 + 2]);
    }
    final uniqueCount = uniq.length;

    // ---- 无限制 / 上限超过实际/调色板规模：直接映射最近色 ----
    if (colorLimit == null || colorLimit <= 0 || colorLimit >= uniqueCount || colorLimit >= P) {
      var idx = palette.closestIndicesBatch(img, n);
      if (icmSmooth > 0) idx = _icmRefine(img, h, w, idx, icmSmooth, metric);
      Uint8List out = _applyIndices(idx);
      if (dither) out = _floydSteinberg(img, h, w, metric, ditherStrength);
      return QuantizeResult(out, _usageFromIndices(idx));
    }

    // ---- 限色：显著性加权 + 色度保持的贪心 K-center ----
    final K = colorLimit;
    final Z = _batchToLab(img, n); // (n,3)
    final weights = _salienceWeights(img, h, w, salience);
    final centerIdx = _selectPaletteColors(img, h, w, Z, weights, K, metric);
    final kEff = centerIdx.length;
    final beadRgb = List<int>.generate(kEff * 3, (i) {
      final c = palette.colors[centerIdx[i ~/ 3]];
      return i % 3 == 0 ? c.r : (i % 3 == 1 ? c.g : c.b);
    });
    final centers = List<Lab>.generate(kEff, (i) => palette.colors[centerIdx[i]].lab);

    // 分配：色度惩罚的最近 bead
    final labels = Int32List(n);
    for (var i = 0; i < n; i++) {
      final pl = Z[i];
      final srcC = sqrt(pl.a * pl.a + pl.b * pl.b);
      var best = 0;
      var bestD = double.infinity;
      for (var kk = 0; kk < kEff; kk++) {
        final cen = centers[kk];
        double d;
        if (metric == 'ciede2000') {
          d = ColorMetric.ciede2000(pl, cen);
        } else {
          final dl = pl.l - cen.l, da = pl.a - cen.a, db = pl.b - cen.b;
          d = dl * dl + da * da + db * db;
        }
        final cenC = sqrt(cen.a * cen.a + cen.b * cen.b);
        double pen;
        if (srcC >= _CHROMA_SAT_MIN) {
          pen = max(0.0, (srcC - _CHROMA_MATCH_TOL) - cenC) * _CHROMA_SOFT_PENALTY;
        } else {
          pen = max(0.0, cenC - (srcC + _CHROMA_ALLOW_BOOST)) * _CHROMA_SOFT_PENALTY;
        }
        final tot = d + pen;
        if (tot < bestD) {
          bestD = tot;
          best = kk;
        }
      }
      labels[i] = best;
    }
    var mappedIdx = Int32List(n);
    for (var i = 0; i < n; i++) mappedIdx[i] = centerIdx[labels[i]];

    if (icmSmooth > 0) {
      mappedIdx = _icmRefine(img, h, w, mappedIdx, icmSmooth, metric);
      // 重新派生 centroid labels 供受限抖动
      for (var i = 0; i < n; i++) {
        final mi = mappedIdx[i];
        labels[i] = centerIdx.indexOf(mi);
      }
    }

    Uint8List out = _applyIndices(mappedIdx);
    if (dither) {
      out = _floydSteinbergToSet(img, h, w, beadRgb, centers, Z, metric, ditherStrength);
    }
    return QuantizeResult(out, _usageFromIndices(mappedIdx));
  }

  // ---- 批量 RGB -> 标准 LAB ----
  List<Lab> _batchToLab(Uint8List pix, int n) {
    final out = List<Lab>.generate(n, (i) => ColorMetric.rgbToLab(pix[i * 3], pix[i * 3 + 1], pix[i * 3 + 2]));
    return out;
  }

  Uint8List _applyIndices(Int32List idx) {
    final out = Uint8List(idx.length * 3);
    for (var i = 0; i < idx.length; i++) {
      final c = palette.colors[idx[i]];
      out[i * 3] = c.r;
      out[i * 3 + 1] = c.g;
      out[i * 3 + 2] = c.b;
    }
    return out;
  }

  Map<String, int> _usageFromIndices(Int32List idx) {
    final u = <String, int>{};
    for (final i in idx) {
      final code = palette.colors[i].code;
      u[code] = (u[code] ?? 0) + 1;
    }
    return u;
  }

  // ---- 显著性权重 = 饱和度 x 对比度 x 稀有度（对应 _salience_weights）----
  Float64List _salienceWeights(Uint8List img, int h, int w, double strength) {
    final n = h * w;
    final sat = Float64List(n);
    final labs = _batchToLab(img, n);
    // 饱和度（HSV 的 S）
    for (var i = 0; i < n; i++) {
      final r = img[i * 3] / 255.0, g = img[i * 3 + 1] / 255.0, b = img[i * 3 + 2] / 255.0;
      final mx = max(r, max(g, b)), mn = min(r, min(g, b));
      sat[i] = mx == 0 ? 0 : (mx - mn) / mx;
    }
    // 局部对比度（LAB 到 3x3 模糊）
    final contrast = Float64List(n);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final i = y * w + x;
        double sl = 0, sa = 0, sb = 0, cnt = 0;
        for (var dy = -1; dy <= 1; dy++) {
          for (var dx = -1; dx <= 1; dx++) {
            final ny = y + dy, nx = x + dx;
            if (ny >= 0 && ny < h && nx >= 0 && nx < w) {
              final j = ny * w + nx;
              sl += labs[j].l; sa += labs[j].a; sb += labs[j].b; cnt++;
            }
          }
        }
        final dl = labs[i].l - sl / cnt, da = labs[i].a - sa / cnt, db = labs[i].b - sb / cnt;
        contrast[i] = sqrt(dl * dl + da * da + db * db);
      }
    }
    double cmax = 1e-6;
    for (final c in contrast) {
      if (c > cmax) cmax = c;
    }
    for (var i = 0; i < n; i++) contrast[i] /= cmax;

    // 稀有度：粗色 bin 频率的倒数
    final bins = Int32List(n);
    final counts = Float64List(512);
    for (var i = 0; i < n; i++) {
      final b = (img[i * 3] ~/ 32) * 64 + (img[i * 3 + 1] ~/ 32) * 8 + (img[i * 3 + 2] ~/ 32);
      bins[i] = b;
      counts[b]++;
    }
    final rarity = Float64List(n);
    double rmax = 1e-6;
    for (var i = 0; i < n; i++) {
      rarity[i] = 1.0 / (counts[bins[i]] + 1e-6);
      if (rarity[i] > rmax) rmax = rarity[i];
    }
    for (var i = 0; i < n; i++) rarity[i] /= rmax;

    final weights = Float64List(n);
    double wsum = 0;
    for (var i = 0; i < n; i++) {
      final r = sqrt(rarity[i].clamp(0.0, 1.0));
      final satTerm = 0.4 + 0.6 * sat[i];
      final conTerm = 0.5 + 0.5 * contrast[i];
      final rarTerm = pow(1.0 + 3.0 * r, strength).toDouble();
      weights[i] = satTerm * conTerm * rarTerm;
      wsum += weights[i];
    }
    final wmean = wsum / n + 1e-9;
    for (var i = 0; i < n; i++) weights[i] /= wmean;
    return weights;
  }

  // ---- 贪心 K-center 选色（对应 _select_palette_colors）----
  List<int> _selectPaletteColors(Uint8List img, int h, int w, List<Lab> Z,
      Float64List weights, int K, String metric) {
    final n = h * w;
    final P = palette.colors.length;
    K = max(1, min(K, P));
    final palLab = palette.colors.map((c) => c.lab).toList();

    // 每像素最近 bead + 权重直方图
    final dpix = List<Float64List>.generate(n, (_) => Float64List(P));
    final nearest = Int32List(n);
    for (var i = 0; i < n; i++) {
      var best = 0, bestD = double.infinity;
      for (var p = 0; p < P; p++) {
        final d = metric == 'ciede2000'
            ? ColorMetric.ciede2000(Z[i], palLab[p])
            : _labSq(Z[i], palLab[p]);
        dpix[i][p] = d;
        if (d < bestD) {
          bestD = d;
          best = p;
        }
      }
      nearest[i] = best;
    }
    final hist = Float64List(P);
    for (var i = 0; i < n; i++) hist[nearest[i]] += weights[i];

    // 候选池
    final order = List<int>.generate(P, (i) => i)..sort((a, b) => hist[b].compareTo(hist[a]));
    final supportN = max(K * 3, K + 6);
    final cand = <int>[];
    for (var i = 0; i < min(supportN, P); i++) {
      if (hist[order[i]] > 0 && !cand.contains(order[i])) cand.add(order[i]);
    }
    if (cand.isEmpty) cand.add(order[0]);

    // 色度惩罚距离矩阵 (n, C)
    final C = cand.length;
    final D = List<Float64List>.generate(n, (_) => Float64List(C));
    for (var i = 0; i < n; i++) {
      final srcC = sqrt(Z[i].a * Z[i].a + Z[i].b * Z[i].b);
      final sat = srcC >= _CHROMA_SAT_MIN;
      for (var ci = 0; ci < C; ci++) {
        final cen = palLab[cand[ci]];
        final cenC = sqrt(cen.a * cen.a + cen.b * cen.b);
        double pen;
        if (sat) {
          pen = max(0.0, (srcC - _CHROMA_MATCH_TOL) - cenC) * _CHROMA_SOFT_PENALTY;
        } else {
          pen = max(0.0, cenC - (srcC + _CHROMA_ALLOW_BOOST)) * _CHROMA_SOFT_PENALTY;
        }
        D[i][ci] = dpix[i][cand[ci]] + pen;
      }
    }

    // 贪心
    var first = 0;
    double hmax = -1;
    for (var p = 0; p < P; p++) {
      if (hist[p] > hmax) {
        hmax = hist[p];
        first = p;
      }
    }
    final chosen = <int>[cand.contains(first) ? first : cand[0]];
    final cpos = {for (var i = 0; i < C; i++) cand[i]: i};
    final bestD = Float64List(n);
    for (var i = 0; i < n; i++) bestD[i] = D[i][cpos[chosen[0]]!];

    while (chosen.length < K && chosen.length < C) {
      var nxt = -1;
      var nxtGain = double.negativeInfinity;
      for (var ci = 0; ci < C; ci++) {
        if (chosen.contains(cand[ci])) continue;
        double gain = 0;
        for (var i = 0; i < n; i++) {
          final imp = max(0.0, bestD[i] - D[i][ci]);
          gain += weights[i] * imp;
        }
        if (gain > nxtGain) {
          nxtGain = gain;
          nxt = ci;
        }
      }
      if (nxt < 0 || !nxtGain.isFinite) break;
      chosen.add(cand[nxt]);
      for (var i = 0; i < n; i++) bestD[i] = min(bestD[i], D[i][nxt]);
    }
    return chosen;
  }

  double _labSq(Lab a, Lab b) {
    final dl = a.l - b.l, da = a.a - b.a, db = a.b - b.b;
    return dl * dl + da * da + db * db;
  }

  // ---- 显著性图（对应 _salience_map，用于 ICM）----
  Float64List _salienceMap(Uint8List img, int h, int w) {
    final n = h * w;
    final labs = _batchToLab(img, n);
    final sat = Float64List(n);
    for (var i = 0; i < n; i++) {
      final r = img[i * 3] / 255.0, g = img[i * 3 + 1] / 255.0, b = img[i * 3 + 2] / 255.0;
      final mx = max(r, max(g, b)), mn = min(r, min(g, b));
      sat[i] = mx == 0 ? 0 : (mx - mn) / mx;
    }
    final contrast = Float64List(n);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final i = y * w + x;
        double sl = 0, sa = 0, sb = 0, cnt = 0;
        for (var dy = -1; dy <= 1; dy++) {
          for (var dx = -1; dx <= 1; dx++) {
            final ny = y + dy, nx = x + dx;
            if (ny >= 0 && ny < h && nx >= 0 && nx < w) {
              final j = ny * w + nx;
              sl += labs[j].l; sa += labs[j].a; sb += labs[j].b; cnt++;
            }
          }
        }
        final dl = labs[i].l - sl / cnt, da = labs[i].a - sa / cnt, db = labs[i].b - sb / cnt;
        contrast[i] = sqrt(dl * dl + da * da + db * db);
      }
    }
    double cmax = 1e-6;
    for (final c in contrast) {
      if (c > cmax) cmax = c;
    }
    final sal = Float64List(n);
    for (var i = 0; i < n; i++) {
      sal[i] = (0.5 * sat[i] + 0.5 * (contrast[i] / cmax)).clamp(0.0, 1.0);
    }
    // 5x5 高斯模糊
    return _gaussianBlur(sal, h, w, 5);
  }

  Float64List _gaussianBlur(Float64List src, int h, int w, int ksize) {
    final r = ksize ~/ 2;
    final sigma = 0.3 * ((ksize - 1) * 0.5 - 1) + 0.8;
    final kernel = Float64List(ksize);
    double ksum = 0;
    for (var i = 0; i < ksize; i++) {
      final d = i - r;
      kernel[i] = exp(-(d * d) / (2 * sigma * sigma));
      ksum += kernel[i];
    }
    for (var i = 0; i < ksize; i++) kernel[i] /= ksum;
    final tmp = Float64List(h * w);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        double s = 0;
        for (var k = -r; k <= r; k++) {
          final xx = (x + k).clamp(0, w - 1);
          s += src[y * w + xx] * kernel[k + r];
        }
        tmp[y * w + x] = s;
      }
    }
    final out = Float64List(h * w);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        double s = 0;
        for (var k = -r; k <= r; k++) {
          final yy = (y + k).clamp(0, h - 1);
          s += tmp[yy * w + x] * kernel[k + r];
        }
        out[y * w + x] = s;
      }
    }
    return out;
  }

  // ---- ICM 空间一致性细化（对应 _icm_refine）----
  Int32List _icmRefine(Uint8List img, int h, int w, Int32List idx, double strength,
      String metric, {int iters = 3}) {
    final n = h * w;
    final L = Int32List.fromList(idx);
    final palLab = palette.colors.map((c) => c.lab).toList();
    final pixLab = _batchToLab(img, n);
    final salience = _salienceMap(img, h, w);
    final lam = Float64List(n);
    for (var i = 0; i < n; i++) {
      lam[i] = strength * (1.0 - 0.7 * salience[i]) * 25.0;
    }

    const dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)];
    for (var it = 0; it < iters; it++) {
      var changed = 0;
      for (var y = 0; y < h; y++) {
        for (var x = 0; x < w; x++) {
          final i = y * w + x;
          final cand = <int>[L[i]];
          for (final d in dirs) {
            final ny = y + d.$1, nx = x + d.$2;
            if (ny >= 0 && ny < h && nx >= 0 && nx < w) {
              final c = L[ny * w + nx];
              if (!cand.contains(c)) cand.add(c);
            }
          }
          if (cand.length == 1) continue;
          final pl = pixLab[i];
          final match = Float64List(cand.length);
          for (final d in dirs) {
            final ny = y + d.$1, nx = x + d.$2;
            if (ny >= 0 && ny < h && nx >= 0 && nx < w) {
              final nl = L[ny * w + nx];
              final ci = cand.indexOf(nl);
              if (ci >= 0) match[ci]++;
            }
          }
          var bestLocal = 0;
          var bestE = double.infinity;
          for (var ci = 0; ci < cand.length; ci++) {
            final ce = metric == 'ciede2000'
                ? ColorMetric.ciede2000(pl, palLab[cand[ci]])
                : _labSq(pl, palLab[cand[ci]]);
            final e = ce - lam[i] * match[ci];
            if (e < bestE) {
              bestE = e;
              bestLocal = ci;
            }
          }
          if (cand[bestLocal] != L[i]) {
            L[i] = cand[bestLocal];
            changed++;
          }
        }
      }
      if (changed == 0) break;
    }
    return L;
  }

  // ---- Floyd-Steinberg 误差扩散（LAB，全调色板；对应 _floyd_steinberg）----
  Uint8List _floydSteinberg(Uint8List img, int h, int w, String metric, double strength) {
    final n = h * w;
    final s = strength.clamp(0.0, 1.0);
    final work = List<Lab>.generate(n, (i) {
      final l = ColorMetric.rgbToLab(img[i * 3], img[i * 3 + 1], img[i * 3 + 2]);
      return l;
    });
    // 用可变数组
    final wl = Float64List(n), wa = Float64List(n), wb = Float64List(n);
    for (var i = 0; i < n; i++) {
      wl[i] = work[i].l; wa[i] = work[i].a; wb[i] = work[i].b;
    }
    final palLab = palette.colors.map((c) => c.lab).toList();
    final out = Uint8List(n * 3);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final i = y * w + x;
        final old = Lab(wl[i], wa[i], wb[i]);
        var k = 0;
        var bestD = double.infinity;
        for (var p = 0; p < palLab.length; p++) {
          final d = metric == 'ciede2000'
              ? ColorMetric.ciede2000(old, palLab[p])
              : _labSq(old, palLab[p]);
          if (d < bestD) {
            bestD = d;
            k = p;
          }
        }
        final bc = palette.colors[k];
        out[i * 3] = bc.r; out[i * 3 + 1] = bc.g; out[i * 3 + 2] = bc.b;
        final el = (old.l - palLab[k].l) * s;
        final ea = (old.a - palLab[k].a) * s;
        final eb = (old.b - palLab[k].b) * s;
        void spread(int j, double f) {
          wl[j] += el * f; wa[j] += ea * f; wb[j] += eb * f;
        }

        if (x + 1 < w) spread(i + 1, 7 / 16);
        if (y + 1 < h) {
          if (x > 0) spread(i + w - 1, 3 / 16);
          spread(i + w, 5 / 16);
          if (x + 1 < w) spread(i + w + 1, 1 / 16);
        }
      }
    }
    return out;
  }

  // ---- 受限 Floyd-Steinberg（对应 _floyd_steinberg_to_set）----
  Uint8List _floydSteinbergToSet(Uint8List img, int h, int w, List<int> beadRgb,
      List<Lab> beadLab, List<Lab> Z, String metric, double strength) {
    final n = h * w;
    final s = strength.clamp(0.0, 1.0);
    final wl = Float64List(n), wa = Float64List(n), wb = Float64List(n);
    for (var i = 0; i < n; i++) {
      wl[i] = Z[i].l; wa[i] = Z[i].a; wb[i] = Z[i].b;
    }
    final out = Uint8List(n * 3);
    final kEff = beadLab.length;
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final i = y * w + x;
        final old = Lab(wl[i], wa[i], wb[i]);
        var k = 0;
        var bestD = double.infinity;
        for (var kk = 0; kk < kEff; kk++) {
          final d = _labSq(old, beadLab[kk]);
          if (d < bestD) {
            bestD = d;
            k = kk;
          }
        }
        out[i * 3] = beadRgb[k * 3];
        out[i * 3 + 1] = beadRgb[k * 3 + 1];
        out[i * 3 + 2] = beadRgb[k * 3 + 2];
        final el = (old.l - beadLab[k].l) * s;
        final ea = (old.a - beadLab[k].a) * s;
        final eb = (old.b - beadLab[k].b) * s;
        void spread(int j, double f) {
          wl[j] += el * f; wa[j] += ea * f; wb[j] += eb * f;
        }

        if (x + 1 < w) spread(i + 1, 7 / 16);
        if (y + 1 < h) {
          if (x > 0) spread(i + w - 1, 3 / 16);
          spread(i + w, 5 / 16);
          if (x + 1 < w) spread(i + w + 1, 1 / 16);
        }
      }
    }
    return out;
  }
}
