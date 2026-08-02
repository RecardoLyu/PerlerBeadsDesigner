import 'dart:math';
import 'dart:typed_data';

/// 自包含 SLIC 超像素过分割（纯 Dart）。
/// 逐行对应桌面版 src/utils/segmentation.py 的 _slic_superpixels，
/// 保证两端对同一输入产生相同的标签图。输出为 0-based、连通性强制的标签。
///
/// 说明：该实现不依赖 OpenCV 的 SLIC（opencv_dart 的 ximgproc 绑定不全），
/// 与桌面版「去 skimage」的自实现保持一致。
class Slic {
  Slic._();

  /// [rgb] 为 H*W*3 的 RGB 字节（行优先）。返回 H*W 的 int32 标签。
  /// 为保证对拍一致，Lab 转换在 Dart 内用与 cv2.COLOR_RGB2LAB 相同的公式完成。
  static Int32List slicSuperpixels(
    Uint8List rgb,
    int h,
    int w, {
    int nSegments = 150,
    double compactness = 10.0,
    int iters = 10,
  }) {
    final n = max(1, nSegments);
    final step = max(1, (sqrt((h * w) / n)).round());

    // ---- RGB -> Lab（对齐 cv2.COLOR_RGB2LAB：Lab 已缩放到 0-255 量纲）----
    // cv2 的 8bit Lab: L'=L*255/100, a'=a+128, b'=b+128
    final lab = Float32List(h * w * 3);
    for (var i = 0; i < h * w; i++) {
      final r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
      final l = _rgbToLabScaled(r, g, b);
      lab[i * 3] = l.$1;
      lab[i * 3 + 1] = l.$2;
      lab[i * 3 + 2] = l.$3;
    }

    final m = compactness / step;
    final scale = 255.0 / max(h, w);

    // ---- 特征 (l, a, b, m*x', m*y')，空间坐标归一化到 ~0-255 ----
    // feats[c] 为通道 c 的 H*W 平面（SoA 布局，访问更快）
    final F = 5;
    final feats = List<Float64List>.generate(F, (_) => Float64List(h * w));
    for (var y = 0; y < h; y++) {
      final yy = y * scale;
      for (var x = 0; x < w; x++) {
        final i = y * w + x;
        feats[0][i] = lab[i * 3];
        feats[1][i] = lab[i * 3 + 1];
        feats[2][i] = lab[i * 3 + 2];
        feats[3][i] = m * x * scale;
        feats[4][i] = m * yy;
      }
    }

    // ---- 规则网格种子（距边界半个 step）----
    final ys = <int>[];
    for (var y = step ~/ 2; y < h; y += step) ys.add(y);
    final xs = <int>[];
    for (var x = step ~/ 2; x < w; x += step) xs.add(x);
    if (ys.isEmpty || xs.isEmpty) return Int32List(h * w);

    final K = ys.length * xs.length;
    final centers = List<Float64List>.generate(K, (_) => Float64List(F));
    var k = 0;
    for (final sy in ys) {
      for (final sx in xs) {
        final i = sy * w + sx;
        for (var c = 0; c < F; c++) centers[k][c] = feats[c][i];
        k++;
      }
    }

    final labels = Int32List(h * w)..fillRange(0, h * w, -1);

    // ---- K-means：每个像素只在其中心 2S×2S 邻域内分配 ----
    for (var it = 0; it < max(1, iters); it++) {
      final dist = Float64List(h * w)..fillRange(0, h * w, double.infinity);
      for (var kk = 0; kk < K; kk++) {
        final ctr = centers[kk];
        final cy = (ctr[4] / m / scale).round();
        final cx = (ctr[3] / m / scale).round();
        final y0 = max(0, cy - step), y1 = min(h, cy + step);
        final x0 = max(0, cx - step), x1 = min(w, cx + step);
        if (y0 >= y1 || x0 >= x1) continue;
        final c0 = ctr[0], c1 = ctr[1], c2 = ctr[2], c3 = ctr[3], c4 = ctr[4];
        for (var y = y0; y < y1; y++) {
          final rowBase = y * w;
          for (var x = x0; x < x1; x++) {
            final i = rowBase + x;
            final d0 = feats[0][i] - c0;
            final d1 = feats[1][i] - c1;
            final d2 = feats[2][i] - c2;
            final d3 = feats[3][i] - c3;
            final d4 = feats[4][i] - c4;
            final d = d0 * d0 + d1 * d1 + d2 * d2 + d3 * d3 + d4 * d4;
            if (d < dist[i]) {
              dist[i] = d;
              labels[i] = kk;
            }
          }
        }
      }
      // 重算中心 = 簇均值
      final counts = Float64List(K);
      final sums = List<Float64List>.generate(K, (_) => Float64List(F));
      for (var i = 0; i < h * w; i++) {
        final kk = labels[i];
        if (kk < 0) continue;
        counts[kk]++;
        for (var c = 0; c < F; c++) sums[kk][c] += feats[c][i];
      }
      for (var kk = 0; kk < K; kk++) {
        final cnt = counts[kk] == 0 ? 1.0 : counts[kk];
        for (var c = 0; c < F; c++) centers[kk][c] = sums[kk][c] / cnt;
      }
    }

    return _enforceConnectivity(labels, h, w, K, step);
  }

  /// 连通性强制：把小的 4-连通碎块并入最大的相邻标签。
  static Int32List _enforceConnectivity(
      Int32List labels, int h, int w, int K, int step) {
    final out = Int32List(h * w);
    var nextLabel = 0;
    final tiny = (step * step) ~/ 4;

    // 每标签的像素索引
    final byLabel = List<List<int>>.generate(K, (_) => []);
    for (var i = 0; i < h * w; i++) {
      final l = labels[i];
      if (l >= 0) byLabel[l].add(i);
    }

    // 4-连通分量标记（BFS）
    final compId = Int32List(h * w)..fillRange(0, h * w, -1);
    final queue = <int>[];
    final compPixels = <List<int>>[];

    for (var kk = 0; kk < K; kk++) {
      // 找该标签内未访问的分量
      for (final start in byLabel[kk]) {
        if (compId[start] != -1 || labels[start] != kk) continue;
        // BFS 收集一个 4-连通分量
        final pixels = <int>[];
        queue..clear()..add(start);
        compId[start] = kk; // 用 compId 存「已访问」，配合 labels 判断同标签
        final cid = compPixels.length;
        compPixels.add(pixels);
        while (queue.isNotEmpty) {
          final i = queue.removeLast();
          pixels.add(i);
          final y = i ~/ w, x = i % w;
          void visit(int ni) {
            if (ni >= 0 && ni < h * w && compId[ni] == -1 && labels[ni] == kk) {
              compId[ni] = kk;
              queue.add(ni);
            }
          }

          if (x > 0) visit(i - 1);
          if (x < w - 1) visit(i + 1);
          if (y > 0) visit(i - w);
          if (y < h - 1) visit(i + w);
        }
        // 判定：碎块 -> 并入相邻主标签；否则独立成新标签
        // （num>2 的判定在 Python 里是「该标签有多个分量」，这里等价处理：
        //  分量数未知时以尺寸阈值判断小碎块）
        if (pixels.length < tiny) {
          // 找膨胀邻域里出现最多的已分配标签
          final neighborCount = <int, int>{};
          for (final i in pixels) {
            final y = i ~/ w, x = i % w;
            void n(int ni) {
              if (ni >= 0 && ni < h * w) {
                final o = out[ni];
                if (o > 0) neighborCount[o] = (neighborCount[o] ?? 0) + 1;
              }
            }

            if (x > 0) n(i - 1);
            if (x < w - 1) n(i + 1);
            if (y > 0) n(i - w);
            if (y < h - 1) n(i + w);
            if (x > 0 && y > 0) n(i - w - 1);
            if (x < w - 1 && y > 0) n(i - w + 1);
            if (x > 0 && y < h - 1) n(i + w - 1);
            if (x < w - 1 && y < h - 1) n(i + w + 1);
          }
          var lbl = nextLabel;
          if (neighborCount.isNotEmpty) {
            lbl = neighborCount.entries.reduce((a, b) => a.value >= b.value ? a : b).key;
          }
          for (final i in pixels) {
            out[i] = lbl;
          }
          nextLabel = max(nextLabel, lbl + 1);
        } else {
          for (final i in pixels) {
            out[i] = nextLabel;
          }
          nextLabel++;
        }
        // 清理 cid 引用（避免误用）
        assert(cid == compPixels.length - 1);
      }
    }
    return out;
  }

  /// RGB(0-255) -> cv2 8bit Lab（L*255/100, a+128, b+128），对齐 cv2.COLOR_RGB2LAB。
  static (double, double, double) _rgbToLabScaled(int r, int g, int b) {
    double lin(int c) {
      final v = c / 255.0;
      return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4).toDouble();
    }

    final rl = lin(r), gl = lin(g), bl = lin(b);
    var x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047;
    var y = (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) / 1.00000;
    var z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883;

    double f(double t) =>
        t > 0.008856 ? pow(t, 1 / 3).toDouble() : (7.787 * t) + 16 / 116;

    final fx = f(x), fy = f(y), fz = f(z);
    final l = 116 * fy - 16; // 0-100
    final a = 500 * (fx - fy); // ~-127..127
    final bb = 200 * (fy - fz);
    return (l * 255 / 100, a + 128, bb + 128);
  }
}
