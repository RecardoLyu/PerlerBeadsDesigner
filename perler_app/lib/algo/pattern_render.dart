import 'dart:typed_data';
import 'basic_adjust.dart';
import 'quantizer.dart';

/// BOM 单条目（对齐桌面版 pattern_generator._create_bom 的每色结构）。
class BomEntry {
  final String code, name, hex;
  final int count;
  final double percentage; // 0-100
  const BomEntry(this.code, this.name, this.hex, this.count, this.percentage);
}

/// 图纸生成的纯 Dart 工具：豆域下采样 / mask 对齐 / code 映射 / BOM 组装。
/// 与 BasicAdjust/Quantizer 一样是**纯 Dart，不碰 OpenCV native**（避开
/// dartcv4 在部分 ABI 的 SIGSEGV），量化在豆域（gw×gh ≈ 万级像素）跑，手机端毫秒级。
class PatternRender {
  PatternRender._();

  /// 盒式平均下采样（对应 cv2.INTER_AREA）：把大图 RGB 缩到 (nw×nh)。
  /// 每个目标豆 = 源图对应矩形框内所有像素的面积加权平均，避免双线性在
  /// 高颜色上限时的摩尔纹/过渡色串色（桌面版 pattern_generator.py:92 注释）。
  /// 仅在缩小（nw<w 或 nh<h）时用盒式平均；等/放大退化为最近邻。
  static Uint8List boxAverageDownsample(
      Uint8List rgb, int w, int h, int nw, int nh) {
    if (nw >= w && nh >= h) {
      // 不缩小：最近邻，与 BasicAdjust.resizeMask 同思想。
      final out = Uint8List(nw * nh * 3);
      for (var y = 0; y < nh; y++) {
        final sy = ((y + 0.5) * h / nh).floor().clamp(0, h - 1);
        for (var x = 0; x < nw; x++) {
          final sx = ((x + 0.5) * w / nw).floor().clamp(0, w - 1);
          final s = (sy * w + sx) * 3, d = (y * nw + x) * 3;
          out[d] = rgb[s];
          out[d + 1] = rgb[s + 1];
          out[d + 2] = rgb[s + 2];
        }
      }
      return out;
    }
    final out = Uint8List(nw * nh * 3);
    // 源图每个像素 (sx,sy) 落入目标豆 (sx*nw/w, sy*nh/h)，做面积加权累积。
    // 简化：边界部分像素按 1 计入所属豆（豆数远小于源像素时误差可忽略，
    // 且这正是 INTER_AREA 在整数倍/常规缩放下的近似）。
    final accR = Float64List(nw * nh);
    final accG = Float64List(nw * nh);
    final accB = Float64List(nw * nh);
    final cnt = Float64List(nw * nh);
    final xScale = nw / w, yScale = nh / h;
    for (var sy = 0; sy < h; sy++) {
      final dy = (sy * yScale).floor().clamp(0, nh - 1);
      for (var sx = 0; sx < w; sx++) {
        final dx = (sx * xScale).floor().clamp(0, nw - 1);
        final di = dy * nw + dx;
        final s = (sy * w + sx) * 3;
        accR[di] += rgb[s];
        accG[di] += rgb[s + 1];
        accB[di] += rgb[s + 2];
        cnt[di] += 1;
      }
    }
    for (var i = 0; i < nw * nh; i++) {
      final c = cnt[i] == 0 ? 1.0 : cnt[i];
      final d = i * 3;
      out[d] = (accR[i] / c).round().clamp(0, 255);
      out[d + 1] = (accG[i] / c).round().clamp(0, 255);
      out[d + 2] = (accB[i] / c).round().clamp(0, 255);
    }
    return out;
  }

  /// 把计算域 mask（0/255，mw*mh）最近邻对齐到豆网格 (gw×gh) → bool 列表。
  /// true = 前景保留豆。对应桌面 app.py 的 (STATE.mask>127) + INTER_NEAREST resize。
  static List<bool> maskToBeadGrid(
      Uint8List mask, int mw, int mh, int gw, int gh) {
    final resized = BasicAdjust.resizeMask(mask, mw, mh, gw, gh);
    return List<bool>.generate(gw * gh, (i) => resized[i] > 127);
  }

  /// 把量化后豆图 (gw×gh, rgb gw*gh*3) 逐豆映射成 code（gw*gh 个）。
  static List<String> buildCodes(
      Palette palette, Uint8List quantRgb, int gw, int gh) {
    return List<String>.generate(gw * gh, (i) {
      final idx = palette.closestIndex(
          quantRgb[i * 3], quantRgb[i * 3 + 1], quantRgb[i * 3 + 2]);
      return palette.colors[idx].code;
    });
  }

  /// 组装 BOM：usage(code->count) + palette → 排序列表（count desc，code 次键）。
  /// beadMask 非空时只统计前景豆（对应 rebuild_bom_with_mask），此时需传 codes。
  static List<BomEntry> buildBom(
    Palette palette,
    Map<String, int> usage,
    int totalBeads, {
    List<bool>? beadMask,
    List<String>? codes,
  }) {
    // mask 时按 codes 重新统计前景豆；否则直接用量化器给的 usage。
    final Map<String, int> counts;
    if (beadMask != null && codes != null) {
      counts = {};
      for (var i = 0; i < codes.length; i++) {
        if (beadMask[i]) counts[codes[i]] = (counts[codes[i]] ?? 0) + 1;
      }
    } else {
      counts = usage;
    }
    final total = counts.values.fold<int>(0, (a, b) => a + b);
    final codeToColor = {for (final c in palette.colors) c.code: c};
    final entries = counts.entries.map((e) {
      final col = codeToColor[e.key];
      return BomEntry(
        e.key,
        col?.name ?? e.key,
        col?.hex ?? '#808080',
        e.value,
        total == 0 ? 0.0 : e.value / total * 100.0,
      );
    }).toList();
    entries.sort((a, b) {
      final d = b.count.compareTo(a.count);
      return d != 0 ? d : a.code.compareTo(b.code);
    });
    return entries;
  }
}
