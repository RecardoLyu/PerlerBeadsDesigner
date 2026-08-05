import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/algo/pattern_pipeline.dart';
import 'package:perler_app/algo/pattern_render.dart';
import 'package:perler_app/algo/quantizer.dart';

/// 构造一个极简调色板（红/绿/蓝/白/黑），不依赖 rootBundle 资源。
Palette _tinyPalette() => Palette([
      BeadColor('R', '红', '#FF0000'),
      BeadColor('G', '绿', '#00FF00'),
      BeadColor('B', '蓝', '#0000FF'),
      BeadColor('W', '白', '#FFFFFF'),
      BeadColor('K', '黑', '#000000'),
    ], metric: 'weighted');

/// 8x8 测试图：左半红、右半蓝（h*w*3）。
Uint8List _src() {
  final rgb = Uint8List(8 * 8 * 3);
  for (var y = 0; y < 8; y++) {
    for (var x = 0; x < 8; x++) {
      final i = (y * 8 + x) * 3;
      if (x < 4) {
        rgb[i] = 255;
      } else {
        rgb[i + 2] = 255;
      }
    }
  }
  return rgb;
}

void main() {
  group('runPatternPipeline（后台 isolate 管线）', () {
    test('与主 isolate 直算结果一致（无 mask）', () {
      final palette = _tinyPalette();
      const gw = 4, gh = 4;
      final input = PatternComputeInput(
        imgRgb: _src(), imgW: 8, imgH: 8, gw: gw, gh: gh,
        colorLimit: null, salience: 1.0, dither: false,
        ditherStrength: 1.0, icmSmooth: 0.0, metric: 'weighted',
        palette: palette, segMask: null, segW: 0, segH: 0,
      );
      final res = runPatternPipeline(input);

      // 主 isolate 逐步直算（旧实现路径）
      final beadRgb = PatternRender.boxAverageDownsample(_src(), 8, 8, gw, gh);
      final qres = Quantizer(palette).quantize(beadRgb, gh, gw);
      final codes = PatternRender.buildCodes(palette, qres.rgb, gw, gh);
      final bom = PatternRender.buildBom(palette, qres.usage, gw * gh);

      expect(res.quantRgb, qres.rgb);
      expect(res.codes, codes);
      expect(res.beadMask, isNull);
      expect(res.totalBeads, gw * gh);
      expect(res.bom.map((e) => e.code), bom.map((e) => e.code));
      expect(res.bom.map((e) => e.count), bom.map((e) => e.count));
    });

    test('有 mask：beadMask 对齐且 BOM 只计前景', () {
      final palette = _tinyPalette();
      const gw = 4, gh = 4;
      // 8x8 mask：左半=255（前景）右半=0
      final mask = Uint8List(8 * 8);
      for (var y = 0; y < 8; y++) {
        for (var x = 0; x < 8; x++) {
          mask[y * 8 + x] = x < 4 ? 255 : 0;
        }
      }
      final input = PatternComputeInput(
        imgRgb: _src(), imgW: 8, imgH: 8, gw: gw, gh: gh,
        colorLimit: null, salience: 1.0, dither: false,
        ditherStrength: 1.0, icmSmooth: 0.0, metric: 'weighted',
        palette: palette, segMask: mask, segW: 8, segH: 8,
      );
      final res = runPatternPipeline(input);

      expect(res.beadMask, isNotNull);
      // 前景豆数 = 4列 × 4行 = 16 的一半 = 左半 = 每行 2 豆 × 4 行 = 8
      expect(res.totalBeads, res.beadMask!.where((b) => b).length);
      // BOM 只含前景色（红），不含蓝
      expect(res.bom.every((e) => e.code == 'R'), isTrue);
    });

    test('结果字段可直接喂 ChartPainter（quantRgb 长度 = gw*gh*3）', () {
      final palette = _tinyPalette();
      const gw = 4, gh = 4;
      final input = PatternComputeInput(
        imgRgb: _src(), imgW: 8, imgH: 8, gw: gw, gh: gh,
        colorLimit: null, salience: 1.0, dither: false,
        ditherStrength: 1.0, icmSmooth: 0.0, metric: 'weighted',
        palette: palette, segMask: null, segW: 0, segH: 0,
      );
      final res = runPatternPipeline(input);
      expect(res.quantRgb.length, gw * gh * 3);
      expect(res.codes.length, gw * gh);
    });
  });
}
