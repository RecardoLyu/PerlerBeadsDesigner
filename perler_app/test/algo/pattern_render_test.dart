import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
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

void main() {
  group('boxAverageDownsample', () {
    test('均匀纯色图下采样保持颜色', () {
      // 4x4 全红 → 2x2 仍全红
      final src = Uint8List(4 * 4 * 3);
      for (var i = 0; i < 4 * 4; i++) {
        src[i * 3] = 255;
      }
      final out = PatternRender.boxAverageDownsample(src, 4, 4, 2, 2);
      expect(out.length, 2 * 2 * 3);
      for (var i = 0; i < 4; i++) {
        expect(out[i * 3], 255);
        expect(out[i * 3 + 1], 0);
        expect(out[i * 3 + 2], 0);
      }
    });

    test('盒式平均：左半红右半蓝 → 中间列平均成紫', () {
      // 4x2，左两列红、右两列蓝 → 2x1，每豆是 2x2 均值
      final src = Uint8List(4 * 2 * 3);
      for (var y = 0; y < 2; y++) {
        for (var x = 0; x < 4; x++) {
          final i = (y * 4 + x) * 3;
          if (x < 2) {
            src[i] = 255; // 红
          } else {
            src[i + 2] = 255; // 蓝
          }
        }
      }
      // 缩到 2x1：左豆=纯红，右豆=纯蓝
      final out = PatternRender.boxAverageDownsample(src, 4, 2, 2, 1);
      expect(out[0], 255);
      expect(out[1], 0);
      expect(out[2], 0);
      expect(out[3], 0);
      expect(out[4], 0);
      expect(out[5], 255);
    });

    test('不缩小时退化为最近邻', () {
      final src = Uint8List.fromList([255, 0, 0]);
      final out = PatternRender.boxAverageDownsample(src, 1, 1, 1, 1);
      expect(out[0], 255);
    });
  });

  group('maskToBeadGrid', () {
    test('mask 对齐到豆网格并二值化', () {
      // 2x2 mask：左上=255 其余=0 → 2x2 网格
      final mask = Uint8List.fromList([255, 0, 0, 0]);
      final grid = PatternRender.maskToBeadGrid(mask, 2, 2, 2, 2);
      expect(grid, [true, false, false, false]);
    });
  });

  group('buildCodes', () {
    test('逐豆映射最近色 code', () {
      final p = _tinyPalette();
      // 2 豆：纯红、纯蓝
      final rgb = Uint8List.fromList([255, 0, 0, 0, 0, 255]);
      final codes = PatternRender.buildCodes(p, rgb, 2, 1);
      expect(codes, ['R', 'B']);
    });
  });

  group('buildBom', () {
    test('无 mask：直接统计 usage，count desc 排序', () {
      final p = _tinyPalette();
      final bom = PatternRender.buildBom(p, {'R': 5, 'B': 10, 'G': 1}, 16);
      expect(bom.length, 3);
      expect(bom[0].code, 'B');
      expect(bom[0].count, 10);
      expect(bom[1].code, 'R');
      expect(bom[2].code, 'G');
      // percentage 总和 ≈ 100
      final sum = bom.fold<double>(0, (a, e) => a + e.percentage);
      expect(sum, closeTo(100.0, 0.001));
    });

    test('有 mask：只统计前景豆', () {
      final p = _tinyPalette();
      // 4 豆：R R B B，mask 只留前两豆 → BOM 只含 R×2
      final codes = ['R', 'R', 'B', 'B'];
      final mask = [true, true, false, false];
      final bom = PatternRender.buildBom(
        p, {'R': 2, 'B': 2}, 4,
        beadMask: mask, codes: codes,
      );
      expect(bom.length, 1);
      expect(bom[0].code, 'R');
      expect(bom[0].count, 2);
      expect(bom[0].percentage, closeTo(100.0, 0.001));
    });

    test('count 并列时按 code 字典序', () {
      final p = _tinyPalette();
      final bom = PatternRender.buildBom(p, {'B': 3, 'R': 3}, 6);
      expect(bom[0].code, 'B'); // B < R
      expect(bom[1].code, 'R');
    });
  });
}
