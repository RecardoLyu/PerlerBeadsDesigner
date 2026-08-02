import 'dart:typed_data';
import 'package:opencv_dart/opencv_dart.dart' as cv;

/// OpenCV 操作封装层：对接 opencv_dart。
/// 对应桌面版 src/utils/segmentation.py 中直接调用 cv2 的部分
/// （GrabCut / 分水岭 / Otsu / 形态学 / 高斯模糊 / 亮度对比度）。
/// 这些在 opencv_dart 里都是同名同参，零算法重写。
///
/// 图像统一用 RGB 字节（Uint8List, h*w*3）进出，内部转 cv.Mat。
class CvOps {
  CvOps._();

  /// dartcv4 native 连通性探针：执行一个最小 OpenCV 操作。
  /// 若 dartcv4 native 库在本机 ABI 上加载/调用失败，这里会抛错或 SIGSEGV。
  /// 返回 true 表示 dartcv4 可用。用于 M2 前的环境自检。
  static bool selfTest() {
    final src = cv.Mat.fromList(4, 4, cv.MatType.CV_8UC3,
        Uint8List.fromList(List.generate(4 * 4 * 3, (i) => (i * 7) % 256)));
    final dst = cv.gaussianBlur(src, (3, 3), 0);
    final ok = dst.rows == 4 && dst.cols == 4;
    src.dispose();
    dst.dispose();
    return ok;
  }

  static cv.Mat _toMat(Uint8List rgb, int h, int w) =>
      cv.Mat.fromList(h, w, cv.MatType.CV_8UC3, rgb);

  static Uint8List _fromMat(cv.Mat m) => m.data;

  // ---- 高斯模糊（对应 applyBasic 的高斯核；ksize 奇数，1=不模糊）----
  static Uint8List gaussianBlur(Uint8List rgb, int h, int w, int ksize) {
    if (ksize <= 1) return rgb;
    final k = ksize % 2 == 0 ? ksize + 1 : ksize;
    final src = _toMat(rgb, h, w);
    final dst = cv.gaussianBlur(src, (k, k), 0);
    final out = _fromMat(dst);
    src.dispose();
    dst.dispose();
    return out;
  }

  // ---- 亮度 + 对比度（对应 alpha*img + beta；brightness/contrast 以 1 为中心）----
  static Uint8List brightnessContrast(
      Uint8List rgb, int h, int w, double brightness, double contrast) {
    final src = _toMat(rgb, h, w);
    // convertTo: dst = src*alpha + beta。对比度绕均值拉伸，亮度整体偏移。
    final beta = (brightness - 1.0) * 255.0 / 2.0;
    final dst = src.convertTo(cv.MatType.CV_8UC3, alpha: contrast, beta: beta);
    final out = _fromMat(dst);
    src.dispose();
    dst.dispose();
    return out;
  }

  // ---- GrabCut 矩形初始化（对应 IterativeGrabCutState.segment_rect）----
  // 返回 0/255 二值 mask（前景=255）。bgd/fgd model 由内部管理以便迭代。
  static Uint8List grabCutRect(Uint8List rgb, int h, int w,
      int x, int y, int rw, int rh, cv.Mat bgdModel, cv.Mat fgdModel,
      {int iters = 5}) {
    final src = _toMat(rgb, h, w);
    final mask = cv.Mat.zeros(h, w, cv.MatType.CV_8UC1);
    cv.grabCut(src, mask, cv.Rect(x, y, rw, rh), bgdModel, fgdModel, iters,
        mode: cv.GC_INIT_WITH_RECT);
    final out = _gcToBinary(mask, h, w);
    src.dispose();
    mask.dispose();
    return out;
  }

  // ---- GrabCut mask 初始化 / 迭代（对应 segment_mask / refine）----
  // [gcValues] 为 h*w 的 GC_* 标签（0=BGD,1=FGD,2=PR_BGD,3=PR_FGD）。
  static Uint8List grabCutMask(Uint8List rgb, int h, int w, Uint8List gcValues,
      cv.Mat bgdModel, cv.Mat fgdModel, {int iters = 5}) {
    final src = _toMat(rgb, h, w);
    final mask = cv.Mat.fromList(h, w, cv.MatType.CV_8UC1, gcValues);
    cv.grabCut(src, mask, cv.Rect(0, 0, 0, 0), bgdModel, fgdModel, iters,
        mode: cv.GC_INIT_WITH_MASK);
    final out = _gcToBinary(mask, h, w);
    src.dispose();
    mask.dispose();
    return out;
  }

  static Uint8List _gcToBinary(cv.Mat mask, int h, int w) {
    final d = mask.data;
    final out = Uint8List(h * w);
    for (var i = 0; i < h * w; i++) {
      final v = d[i];
      out[i] = (v == cv.GC_FGD || v == cv.GC_PR_FGD) ? 255 : 0;
    }
    return out;
  }

  static (cv.Mat, cv.Mat) newGrabCutModels() => (
        cv.Mat.zeros(1, 65, cv.MatType.CV_64FC1),
        cv.Mat.zeros(1, 65, cv.MatType.CV_64FC1),
      );

  // ---- Otsu 自动阈值（对应 otsu_segment，自动定向使中央为前景）----
  static Uint8List otsuSegment(Uint8List rgb, int h, int w) {
    final src = _toMat(rgb, h, w);
    var gray = cv.cvtColor(src, cv.COLOR_RGB2GRAY);
    gray = cv.gaussianBlur(gray, (5, 5), 0);
    final bw = cv.threshold(gray, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU).$2;
    final bwInv = cv.threshold(gray, 0, 255, cv.THRESH_BINARY_INV + cv.THRESH_OTSU).$2;
    // 中央区域定向。m 是 bw 或 bwInv 的别名，绝不能单独 dispose（否则双重释放 → cv_Mat_close 崩溃）。
    final useBw = _centerMean(bw, h, w) >= _centerMean(bwInv, h, w);
    final m = useBw ? bw : bwInv;
    final kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3));
    final closed = cv.morphologyEx(m, cv.MORPH_CLOSE, kernel, iterations: 1);
    final out = _fromMat(closed);
    src.dispose(); gray.dispose(); bw.dispose(); bwInv.dispose();
    kernel.dispose(); closed.dispose();
    return out;
  }

  static double _centerMean(cv.Mat m, int h, int w) {
    final d = m.data;
    double sum = 0;
    int cnt = 0;
    for (var y = h ~/ 4; y < 3 * h ~/ 4; y++) {
      for (var x = w ~/ 4; x < 3 * w ~/ 4; x++) {
        sum += d[y * w + x];
        cnt++;
      }
    }
    return cnt == 0 ? 0 : sum / cnt;
  }

  // ---- 分水岭自动分割（对应 watershed_auto）----
  // 注：dartcv4 的 watershed/connectedComponents/distanceTransform 在本机 ABI 上会
  // SIGSEGV(cv_Mat_close fault addr 0x38，native 空结构体解引用)，故这里**绕开这三个
  // native 调用**：threshold/morphology 仍用 OpenCV（Otsu 已验证可用），
  // 距离变换/连通域/种子扩散用纯 Dart 实现，逻辑与桌面版 watershed_auto 等价。
  static Uint8List watershedAuto(Uint8List rgb, int h, int w, {double fgRatio = 0.4}) {
    final created = <cv.Mat>[];
    cv.Mat own(cv.Mat m) { created.add(m); return m; }
    try {
      final src = own(_toMat(rgb, h, w));
      final gray = own(cv.cvtColor(src, cv.COLOR_RGB2GRAY));
      final blurred = own(cv.gaussianBlur(gray, (5, 5), 0));
      final bw = own(cv.threshold(blurred, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU).$2);
      final bwInv = own(cv.threshold(blurred, 0, 255, cv.THRESH_BINARY_INV + cv.THRESH_OTSU).$2);
      final fg = _centerMean(bw, h, w) >= _centerMean(bwInv, h, w) ? bw : bwInv;
      final fgBytes = Uint8List.fromList(fg.data); // 拷出，之后可安全 dispose

      // 开运算去噪（小 Dart 卷积太慢，用 OpenCV morphologyEx——已验证安全）
      final kernel = own(cv.getStructuringElement(cv.MORPH_RECT, (3, 3)));
      final fgMat = own(cv.Mat.fromList(h, w, cv.MatType.CV_8UC1, fgBytes));
      final opening = own(cv.morphologyEx(fgMat, cv.MORPH_OPEN, kernel, iterations: 2));
      final openBytes = opening.data;

      // 纯 Dart：distanceTransform 的替代——用「距背景的近似距离」取 sure-foreground 种子。
      // 简化：对 opening 做两遍 chamfer 距离（3x3），等价于 L2 距离变换的效果。
      final dist = _chamferDistance(openBytes, h, w);
      double maxDist = 0;
      for (final v in dist) { if (v > maxDist) maxDist = v; }
      if (maxDist <= 0) maxDist = 1.0;
      final seedThresh = fgRatio * maxDist;

      // sureFg 种子 + sureBg 背景（opening 膨胀近似），其余为 unknown
      final label = Int32List(h * w); // 0=unknown, 1=bg, >=2=fg 分量
      // 背景 = 非前景 直接当 bg 标签 1
      for (var i = 0; i < h * w; i++) {
        if (openBytes[i] == 0) label[i] = 1;
      }
      // sureFg 种子做连通域标记（纯 Dart 两遍法），标签从 2 起
      var nextLabel = 2;
      final stack = <int>[];
      for (var i = 0; i < h * w; i++) {
        if (label[i] != 0 || dist[i] < seedThresh) continue;
        // BFS 洪泛一个种子连通域
        stack..clear()..add(i);
        label[i] = nextLabel;
        while (stack.isNotEmpty) {
          final cur = stack.removeLast();
          final cx = cur % w, cy = cur ~/ w;
          for (var dy = -1; dy <= 1; dy++) {
            for (var dx = -1; dx <= 1; dx++) {
              if (dx == 0 && dy == 0) continue;
              final nx = cx + dx, ny = cy + dy;
              if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
              final ni = ny * w + nx;
              if (label[ni] == 0 && dist[ni] >= seedThresh) {
                label[ni] = nextLabel;
                stack.add(ni);
              }
            }
          }
        }
        nextLabel++;
      }

      // 分水岭种子扩散（priority 用距离：越靠近种子中心越先扩张），unknown 区域被
      // 最近的种子标签填充。用简单多轮 BFS 扩张直到无 unknown。
      _propagateLabels(label, dist, h, w);

      final out = Uint8List(h * w);
      for (var i = 0; i < h * w; i++) {
        out[i] = label[i] >= 2 ? 255 : 0;
      }
      return out;
    } finally {
      for (final m in created) { m.dispose(); }
    }
  }

  /// 两遍 chamfer(3-4) 距离变换：返回每个前景像素到最近背景的距离（近似 L2）。
  /// 等价 cv2.distanceTransform 的用途（取 sure-foreground 种子）。
  static Float64List _chamferDistance(Uint8List bin, int h, int w) {
    const inf = 1e9;
    final d = Float64List(h * w);
    for (var i = 0; i < h * w; i++) { d[i] = bin[i] > 0 ? inf : 0; }
    // 前向
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final i = y * w + x;
        if (d[i] == 0) continue;
        var m = d[i];
        if (x > 0 && d[i - 1] + 3 < m) m = d[i - 1] + 3;
        if (y > 0 && d[i - w] + 3 < m) m = d[i - w] + 3;
        if (x > 0 && y > 0 && d[i - w - 1] + 4 < m) m = d[i - w - 1] + 4;
        if (x < w - 1 && y > 0 && d[i - w + 1] + 4 < m) m = d[i - w + 1] + 4;
        d[i] = m;
      }
    }
    // 后向
    for (var y = h - 1; y >= 0; y--) {
      for (var x = w - 1; x >= 0; x--) {
        final i = y * w + x;
        var m = d[i];
        if (x < w - 1 && d[i + 1] + 3 < m) m = d[i + 1] + 3;
        if (y < h - 1 && d[i + w] + 3 < m) m = d[i + w] + 3;
        if (x < w - 1 && y < h - 1 && d[i + w + 1] + 4 < m) m = d[i + w + 1] + 4;
        if (x > 0 && y < h - 1 && d[i + w - 1] + 4 < m) m = d[i + w - 1] + 4;
        d[i] = m;
      }
    }
    return d;
  }

  /// 从种子标签向外扩张，把 unknown(0) 像素标记为邻居标签（模拟分水岭淹没）。
  /// 两阶段：先让所有像素被最近的种子标签填充（前景/背景一起 BFS），再保证无 0。
  /// 用迭代加深的多源 BFS，原地修改 label，过程有界（每像素只入队一次）。
  static void _propagateLabels(Int32List label, Float64List dist, int h, int w) {
    // 多源 BFS：把所有已标记像素入队，逐层向外吞并 unknown。
    // dist 仅用于决定同层扩张顺序的稳定性，这里按先进先出即可。
    final queue = <int>[];
    for (var i = 0; i < h * w; i++) { if (label[i] != 0) queue.add(i); }
    var head = 0;
    while (head < queue.length) {
      final cur = queue[head++];
      final cx = cur % w, cy = cur ~/ w;
      final cl = label[cur];
      for (var dy = -1; dy <= 1; dy++) {
        for (var dx = -1; dx <= 1; dx++) {
          if (dx == 0 && dy == 0) continue;
          final nx = cx + dx, ny = cy + dy;
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          final ni = ny * w + nx;
          if (label[ni] == 0) {
            label[ni] = cl;
            queue.add(ni);
          }
        }
      }
    }
  }

  // ---- 形态学（对应 morph_*；shape 见 get_kernel）----
  // shape: 'ellipse' | 'rect' | 'cross' | 'vline' | 'hline' | 'diamond'
  static Uint8List morphology(Uint8List mask, int h, int w, String op,
      int kernelSize, String shape) {
    final k = kernelSize % 2 == 0 ? kernelSize + 1 : kernelSize;
    final kernel = _getKernel(shape, k);
    final src = _toMatGray(mask, h, w);
    cv.Mat dst;
    switch (op) {
      case 'open':
        dst = cv.morphologyEx(src, cv.MORPH_OPEN, kernel, iterations: 1);
        break;
      case 'close':
        dst = cv.morphologyEx(src, cv.MORPH_CLOSE, kernel, iterations: 1);
        break;
      case 'erode':
        dst = cv.erode(src, kernel, iterations: 1,
            borderType: cv.BORDER_CONSTANT, borderValue: cv.Scalar.all(0));
        break;
      case 'dilate':
        dst = cv.dilate(src, kernel, iterations: 1,
            borderType: cv.BORDER_CONSTANT, borderValue: cv.Scalar.all(0));
        break;
      default:
        dst = cv.morphologyEx(src, cv.MORPH_OPEN, kernel, iterations: 1);
    }
    final out = _fromMat(dst);
    src.dispose(); kernel.dispose(); dst.dispose();
    return out;
  }

  static cv.Mat _toMatGray(Uint8List gray, int h, int w) =>
      cv.Mat.fromList(h, w, cv.MatType.CV_8UC1, gray);

  static cv.Mat _getKernel(String shape, int k) {
    switch (shape) {
      case 'rect':
        return cv.getStructuringElement(cv.MORPH_RECT, (k, k));
      case 'cross':
        return cv.getStructuringElement(cv.MORPH_CROSS, (k, k));
      case 'vline':
        return cv.Mat.ones(k, 1, cv.MatType.CV_8UC1);
      case 'hline':
        return cv.Mat.ones(1, k, cv.MatType.CV_8UC1);
      case 'diamond':
        final r = k ~/ 2;
        final buf = Uint8List(k * k);
        for (var y = 0; y < k; y++) {
          for (var x = 0; x < k; x++) {
            buf[y * k + x] = ((x - r).abs() + (y - r).abs()) <= r ? 1 : 0;
          }
        }
        return cv.Mat.fromList(k, k, cv.MatType.CV_8UC1, buf);
      case 'ellipse':
      default:
        return cv.getStructuringElement(cv.MORPH_ELLIPSE, (k, k));
    }
  }

  // ---- SLIC 标签聚合为前景 mask（对应 slic_segment 后半段）----
  // [segments] 为 h*w 的 int32 超像素标签。按饱和度（近灰时退化为亮度）给
  // 每个超像素打分 → Otsu 分前后景 → 中央定向，输出 0/255 二值 mask。
  static Uint8List slicAggregate(Uint8List rgb, int h, int w, Int32List segments) {
    final src = _toMat(rgb, h, w);
    final hsv = cv.cvtColor(src, cv.COLOR_RGB2HSV);
    final grayM = cv.cvtColor(src, cv.COLOR_RGB2GRAY);
    final hsvData = hsv.data, grayData = grayM.data;

    // 标签数
    var maxLabel = 0;
    for (final l in segments) { if (l > maxLabel) maxLabel = l; }
    final K = maxLabel + 1;

    // 每个超像素的饱和度/亮度均值
    final satSum = Float64List(K);
    final graySum = Float64List(K);
    final counts = Int32List(K);
    for (var i = 0; i < h * w; i++) {
      final lb = segments[i];
      counts[lb]++;
      satSum[lb] += hsvData[i * 3 + 1]; // S 通道
      graySum[lb] += grayData[i];
    }
    final feature = Float64List(K);
    var satMin = double.infinity, satMax = -double.infinity;
    for (var k = 0; k < K; k++) {
      final c = counts[k] == 0 ? 1 : counts[k];
      final satMean = satSum[k] / c;
      if (satMean < satMin) satMin = satMean;
      if (satMean > satMax) satMax = satMean;
    }
    final useSat = (satMax - satMin) > 25;
    var fMin = double.infinity, fMax = -double.infinity;
    for (var k = 0; k < K; k++) {
      final c = counts[k] == 0 ? 1 : counts[k];
      final f = useSat ? satSum[k] / c : graySum[k] / c;
      feature[k] = f;
      if (f < fMin) fMin = f;
      if (f > fMax) fMax = f;
    }

    // Otsu 阈值（对 feature 量化到 0-255）；退化时用中点
    final featU8 = Uint8List(K);
    final span = (fMax - fMin) < 1e-6 ? 1.0 : (fMax - fMin);
    for (var k = 0; k < K; k++) {
      featU8[k] = (((feature[k] - fMin) / span) * 255).round().clamp(0, 255);
    }
    final featMat = cv.Mat.fromList(1, K, cv.MatType.CV_8UC1, featU8);
    var thresh = cv.threshold(featMat, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU).$1;
    featMat.dispose();
    // 映射回原 feature 量纲
    final threshFeat = fMin + (thresh / 255.0) * span;
    var highCount = 0;
    for (var k = 0; k < K; k++) { if (feature[k] >= threshFeat) highCount++; }
    final frac = highCount / K;
    double finalThresh = threshFeat;
    if (frac < 0.02 || frac > 0.98) finalThresh = (fMin + fMax) / 2.0;

    // high_fg：feature>=thresh 的超像素为候选前景
    final highFg = List<bool>.generate(K, (k) => feature[k] >= finalThresh);

    // 中央定向：比较中央区域捕获的 feature 质量占比
    final cy1 = h ~/ 4, cy2 = 3 * h ~/ 4, cx1 = w ~/ 4, cx2 = 3 * w ~/ 4;
    double totalMass = 0, centralMass = 0;
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final f = feature[segments[y * w + x]];
        totalMass += f;
        if (y >= cy1 && y < cy2 && x >= cx1 && x < cx2) centralMass += f;
      }
    }
    final centralRatio = totalMass > 0 ? centralMass / totalMass : 0.0;
    final fgIsHigh = centralRatio >= 0.5;

    // 生成 mask
    final out = Uint8List(h * w);
    for (var i = 0; i < h * w; i++) {
      final isHigh = highFg[segments[i]];
      final isFg = fgIsHigh ? isHigh : !isHigh;
      out[i] = isFg ? 255 : 0;
    }

    src.dispose(); hsv.dispose(); grayM.dispose();
    return out;
  }
}
