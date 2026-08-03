import 'dart:typed_data';
import 'package:image/image.dart' as img;

/// 基本图像调整：亮度/对比度/高斯模糊。
/// 纯 Dart 实现（基于 image 包），不依赖 OpenCV/dartcv4 native ——
/// 这些逐像素/卷积操作纯 Dart 足够快，且避开 native FFI 的稳定性风险。
/// OpenCV 只保留给 M2 的真正 CV 算法（GrabCut/分水岭/形态学）。
class BasicAdjust {
  BasicAdjust._();

  /// 亮度 + 对比度，绕均值拉伸。
  /// [brightness]/[contrast] 以 1.0 为不变。对应桌面版 alpha*img+beta 的观感。
  /// 直接修改并返回新的 RGB 字节（h*w*3）。
  static Uint8List brightnessContrast(
      Uint8List rgb, int w, int h, double brightness, double contrast) {
    final out = Uint8List.fromList(rgb); // 副本，不改原图
    // 亮度：整体偏移（映射到 -127..127）；对比度：绕 128 拉伸
    final beta = (brightness - 1.0) * 255.0 / 2.0;
    for (var i = 0; i < out.length; i++) {
      var v = out[i].toDouble();
      // 先对比度（绕 128 拉伸），再亮度（平移）
      v = (v - 128.0) * contrast + 128.0 + beta;
      out[i] = v < 0 ? 0 : (v > 255 ? 255 : v.round());
    }
    return out;
  }

  /// 高斯模糊（radius 为像素半径；<=0 不模糊）。
  /// 用 image 包的高斯实现，质量与 OpenCV 相当。
  static Uint8List gaussianBlur(Uint8List rgb, int w, int h, int radius) {
    if (radius <= 0) return rgb;
    // 包装成 image.Image（RGB）
    final im = img.Image.fromBytes(
      width: w,
      height: h,
      bytes: rgb.buffer,
      order: img.ChannelOrder.rgb,
    );
    final blurred = img.gaussianBlur(im, radius: radius);
    // 读回 RGB 字节
    final out = Uint8List(w * h * 3);
    var i = 0;
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final px = blurred.getPixel(x, y);
        out[i] = px.r.toInt();
        out[i + 1] = px.g.toInt();
        out[i + 2] = px.b.toInt();
        i += 3;
      }
    }
    return out;
  }

  /// 裁剪 RGB 图到矩形 (x,y,cw,ch)。纯 Dart 逐行切片拷贝。自动 clamp 到图内。
  static Uint8List cropRgb(Uint8List rgb, int w, int h, int x, int y, int cw, int ch) {
    // 边界 clamp
    var x0 = x.clamp(0, w), y0 = y.clamp(0, h);
    var x1 = (x + cw).clamp(0, w), y1 = (y + ch).clamp(0, h);
    if (x0 > x1) { final t = x0; x0 = x1; x1 = t; }
    if (y0 > y1) { final t = y0; y0 = y1; y1 = t; }
    final nw = (x1 - x0).clamp(1, w), nh = (y1 - y0).clamp(1, h);
    final out = Uint8List(nw * nh * 3);
    for (var r = 0; r < nh; r++) {
      final srcRow = ((y0 + r) * w + x0) * 3;
      final dstRow = r * nw * 3;
      out.setRange(dstRow, dstRow + nw * 3, rgb, srcRow);
    }
    return out;
  }

  /// 双线性缩小 RGB 图到 (nw,nh)。纯 Dart，用于把大图缩到 CV 可承受的尺寸。
  static Uint8List resizeRgb(Uint8List rgb, int w, int h, int nw, int nh) {
    final out = Uint8List(nw * nh * 3);
    for (var y = 0; y < nh; y++) {
      final fy = (y + 0.5) * h / nh - 0.5;
      final y0 = fy.floor().clamp(0, h - 1);
      final y1 = (y0 + 1).clamp(0, h - 1);
      final wy = fy - y0;
      for (var x = 0; x < nw; x++) {
        final fx = (x + 0.5) * w / nw - 0.5;
        final x0 = fx.floor().clamp(0, w - 1);
        final x1 = (x0 + 1).clamp(0, w - 1);
        final wx = fx - x0;
        final d = (y * nw + x) * 3;
        for (var c = 0; c < 3; c++) {
          final p00 = rgb[(y0 * w + x0) * 3 + c].toDouble();
          final p01 = rgb[(y0 * w + x1) * 3 + c].toDouble();
          final p10 = rgb[(y1 * w + x0) * 3 + c].toDouble();
          final p11 = rgb[(y1 * w + x1) * 3 + c].toDouble();
          final top = p00 + (p01 - p00) * wx;
          final bot = p10 + (p11 - p10) * wx;
          out[d + c] = (top + (bot - top) * wy).round().clamp(0, 255);
        }
      }
    }
    return out;
  }

  /// 最近邻放大 0/255 掩码到 (nw,nh)。纯 Dart。
  static Uint8List resizeMask(Uint8List mask, int w, int h, int nw, int nh) {
    final out = Uint8List(nw * nh);
    for (var y = 0; y < nh; y++) {
      final sy = ((y + 0.5) * h / nh).floor().clamp(0, h - 1);
      for (var x = 0; x < nw; x++) {
        final sx = ((x + 0.5) * w / nw).floor().clamp(0, w - 1);
        out[y * nw + x] = mask[sy * w + sx];
      }
    }
    return out;
  }
}
