import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/algo/basic_adjust.dart';

Uint8List _grad(int w, int h) {
  // R 通道存 x 坐标，便于校验裁剪偏移
  final rgb = Uint8List(w * h * 3);
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      final i = (y * w + x) * 3;
      rgb[i] = x % 256;
      rgb[i + 1] = y % 256;
      rgb[i + 2] = 0;
    }
  }
  return rgb;
}

void main() {
  test('cropRgb 裁剪尺寸与偏移正确', () {
    final rgb = _grad(100, 80);
    final out = BasicAdjust.cropRgb(rgb, 100, 80, 10, 5, 50, 45);
    expect(out.length, 50 * 45 * 3);
    // 左上角 (10,5)：R=x=10, G=y=5
    expect(out[0], 10);
    expect(out[1], 5);
    // 区域内 (10+7, 5+9)：R=17, G=14
    final i = (9 * 50 + 7) * 3;
    expect(out[i], 17);
    expect(out[i + 1], 14);
  });

  test('cropRgb 越界自动 clamp', () {
    final rgb = _grad(100, 80);
    // x2 超出宽度 → 裁到右边界
    final out = BasicAdjust.cropRgb(rgb, 100, 80, 90, 0, 50, 80);
    expect(out.length, 10 * 80 * 3);
    expect(out[0], 90);
  });

  test('cropRgb 反向坐标自动交换', () {
    final rgb = _grad(100, 80);
    final out = BasicAdjust.cropRgb(rgb, 100, 80, 60, 50, 10 - 60, 5 - 50);
    // x 60→10, y 50→5：宽50 高45
    expect(out.length, 50 * 45 * 3);
    expect(out[0], 10);
    expect(out[1], 5);
  });
}
