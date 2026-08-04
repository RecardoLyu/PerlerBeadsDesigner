import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/theme/skin.dart';

/// 皮肤功能测试：
/// - 提取：纯红/灰/黑/白(→空表)/白底红块(score 加权)/真实多彩图(回归手动播种崩溃)
/// - 推导：3 个基准色亮/暗 primary 与桌面端 skin.js 同一套规则（金标准 hex）
///   允差 ±2/通道（浮点舍入）
/// - 模糊三档常量
Uint8List _solid(int r, int g, int b, {int w = 100, int h = 100}) {
  final out = Uint8List(w * h * 3);
  for (var i = 0; i < w * h; i++) {
    out[i * 3] = r;
    out[i * 3 + 1] = g;
    out[i * 3 + 2] = b;
  }
  return out;
}

/// 竖/横三色块拼成一张多彩图（模拟真实照片的多色域）
Uint8List _tricolor(int w, int h) {
  final out = Uint8List(w * h * 3);
  void fill(int y0, int y1, int x0, int x1, int r, int g, int b) {
    for (var y = y0; y < y1; y++) {
      for (var x = x0; x < x1; x++) {
        final i = (y * w + x) * 3;
        out[i] = r; out[i + 1] = g; out[i + 2] = b;
      }
    }
  }
  fill(0, h ~/ 2, 0, w, 111, 164, 203);          // 天空蓝
  fill(h ~/ 2, h, 0, w ~/ 2, 71, 140, 60);        // 草绿
  fill(h ~/ 2, h, w ~/ 2, w, 200, 40, 40);        // 红花
  return out;
}

void _expectColorClose(Color got, String hex, {int tol = 2}) {
  final e = int.parse(hex.substring(1), radix: 16);
  final er = (e >> 16) & 255, eg = (e >> 8) & 255, eb = e & 255;
  final gr = (got.r * 255).round(), gg = (got.g * 255).round(), gb = (got.b * 255).round();
  expect((gr - er).abs() <= tol, true,
      reason: '期望 $hex，得到 #${gr.toRadixString(16).padLeft(2, '0')}'
          '${gg.toRadixString(16).padLeft(2, '0')}'
          '${gb.toRadixString(16).padLeft(2, '0')}');
  expect((gg - eg).abs() <= tol, true);
  expect((gb - eb).abs() <= tol, true);
}

void main() {
  group('extractDominantColors', () {
    test('纯红 → 红为主色', () {
      final got = extractDominantColors(_solid(255, 0, 0), 100, 100);
      expect(got, isNotEmpty);
      expect((got[0] >> 16) & 0xFF, greaterThan(200));
    });

    test('50% 灰 → 空表（无彩色簇）', () {
      expect(extractDominantColors(_solid(128, 128, 128), 100, 100), isEmpty);
    });

    test('纯黑 → 空表', () {
      expect(extractDominantColors(_solid(0, 0, 0), 100, 100), isEmpty);
    });

    test('纯白 → 空表', () {
      expect(extractDominantColors(_solid(255, 255, 255), 100, 100), isEmpty);
    });

    test('白底小红块 → score=count*饱和度 选中红色主体', () {
      final img = _solid(255, 255, 255);
      for (var y = 30; y < 70; y++) {
        for (var x = 30; x < 70; x++) {
          final i = (y * 100 + x) * 3;
          img[i] = 255; img[i + 1] = 0; img[i + 2] = 0;
        }
      }
      final got = extractDominantColors(img, 100, 100);
      expect(got, isNotEmpty);
      expect((got[0] >> 16) & 0xFF, greaterThan(200), reason: '主体应是红色');
    });

    test('真实多彩图（多色域）→ 取到彩色（回归手动播种崩溃）', () {
      final got = extractDominantColors(_tricolor(300, 200), 300, 200);
      expect(got, isNotEmpty, reason: '多彩真实感应能取到主体色');
      expect(got.length, lessThanOrEqualTo(kSkinMaxColors));
    });

    test('返回数量 ≤ kSkinMaxColors', () {
      final got = extractDominantColors(_tricolor(300, 200), 300, 200);
      expect(got.length, lessThanOrEqualTo(kSkinMaxColors));
    });
  });

  group('模糊三档常量', () {
    test('三档 sigma：无/中/高', () {
      expect(kSkinBlurSigma.length, 3);
      expect(kSkinBlurSigma[0], 0);
      expect(kSkinBlurSigma[1], greaterThan(0));
      expect(kSkinBlurSigma[2], greaterThan(kSkinBlurSigma[1]));
    });
  });

  group('deriveSkinPalette 金标准（与桌面端 skin.js 同规则）', () {
    // 基准色 → 亮/暗 primary 期望 hex（Python colorsys 同式预计算）
    const golden = {
      0xFFE11D48: ('#E11D48', '#E64C6E'),
      0xFF0EA5E9: ('#19A1DE', '#4CB6E6'),
      0xFF6B8E6B: ('#44B544', '#70C270'),
    };

    golden.forEach((base, pair) {
      final hex = '#${(base & 0xFFFFFF).toRadixString(16).toUpperCase()}';
      test('基色 $hex', () {
        final light = deriveSkinPalette(Color(base), Brightness.light);
        final dark = deriveSkinPalette(Color(base), Brightness.dark);
        _expectColorClose(light.primary, pair.$1);
        _expectColorClose(dark.primary, pair.$2);
        // 结构不变式：亮色主色上白字、暗色主色明显更亮
        expect(light.onPrimary, const Color(0xFFFFFFFF));
        expect(dark.primary.computeLuminance(),
            greaterThan(light.primary.computeLuminance()));
        // 渐变对色相跟随（violet 偏 h-18°，violetDeep 偏 h+10°，均非默认紫）
        expect(light.violet, isNot(equals(light.primary)));
        expect((light.border.a * 255).round(), lessThan(255));
        // bg/bg2 带 alpha（让页面渐变变薄露出壁纸）
        expect((light.bg.a * 255).round(), lessThan(255));
        expect((dark.bg2.a * 255).round(), lessThan(255));
      });
    });
  });

  group('rgbToHsl / hslToRgb 往返', () {
    for (final rgb in [
      [225, 29, 72],
      [14, 165, 233],
      [107, 142, 107],
      [200, 200, 200],
    ]) {
      test('rgb(${rgb[0]},${rgb[1]},${rgb[2]}) 往返', () {
        final hsl = rgbToHsl(rgb[0], rgb[1], rgb[2]);
        final back = hslToRgb(hsl[0], hsl[1], hsl[2]);
        expect((back[0] - rgb[0]).abs() <= 1, true);
        expect((back[1] - rgb[1]).abs() <= 1, true);
        expect((back[2] - rgb[2]).abs() <= 1, true);
      });
    }
  });
}
