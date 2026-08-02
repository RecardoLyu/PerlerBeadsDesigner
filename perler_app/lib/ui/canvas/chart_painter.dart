import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../../algo/pattern_render.dart';
import '../../algo/quantizer.dart';

/// 完整图纸渲染（对应桌面版 pattern_generator.render_standard_chart）。
/// 布局：豆格(填色+每豆code) + 网格线(minor浅/major深) + 左上坐标刻度 +
/// 底部 BOM 条(统一圆角 chip：左2/5色块+code、右3/5数量，按 count desc 换行)。
/// 用 ui.PictureRecorder 离线录制一次成 ui.Image（非每帧），画布直接显示。
class ChartPainter {
  ChartPainter._();

  static const double _maskFade = 0.70; // 对应桌面 MASK_FADE
  static const int _majorEvery = 5;

  /// 渲染完整图纸为 ui.Image。
  /// [quantRgb] 量化后豆图 (gw×gh, gw*gh*3)；[codes] 每豆 code；
  /// [beadMask] 非空则背景豆淡化；[palette] 解析色块 RGB。
  /// [cellPx] 每豆像素（桌面超采样等效：直接以较大 cellPx 录制，省去二次降采样）。
  static Future<ui.Image> render({
    required Uint8List quantRgb,
    required int gw,
    required int gh,
    required List<String> codes,
    required Palette palette,
    required List<BomEntry> bom,
    List<bool>? beadMask,
    int cellPx = 28,
    bool fadeMasked = true,
    String maskBg = 'none', // none=淡化 | white=纯白 | black=纯黑（对应桌面 MASK 背景）
  }) {
    final codeToColor = {for (final c in palette.colors) c.code: c};
    Color codeRgb(String code, int fallback) {
      final c = codeToColor[code];
      if (c != null) return Color.fromARGB(255, c.r, c.g, c.b);
      return Color(fallback | 0xFF000000);
    }

    final cell = cellPx.toDouble();
    final useFade = fadeMasked && beadMask != null && maskBg == 'none';
    final solidBg = maskBg == 'white'
        ? const Color(0xFFFFFFFF)
        : (maskBg == 'black' ? const Color(0xFF000000) : null);

    // --- 几何（照搬桌面 485-550 行） ---
    final leftMargin = cell * 2 + 6;   // 左侧刻度数字
    final topMargin = cell + 10;       // 顶部刻度数字
    final gridW = gw * cell;
    final gridH = gh * cell;

    // BOM chip 度量
    final sw = cell;
    final barFontSize = (cell * 0.7).clamp(10.0, 1e9);
    final padX = (cell / 3).clamp(8.0, 1e9);
    final chipH = (sw + 2) > (barFontSize + 10) ? sw + 2 : barFontSize + 10;
    final radius = (chipH / 2).clamp(8.0, 1e9);

    // 量文字宽（用 TextPainter）
    double textW(String s, double size,
        {FontWeight weight = FontWeight.normal}) {
      final tp = TextPainter(
        text: TextSpan(
            text: s, style: TextStyle(fontSize: size, fontWeight: weight)),
        textDirection: ui.TextDirection.ltr,
      )..layout();
      return tp.width;
    }

    double maxCodeW = 0, maxCountW = 0;
    for (final e in bom) {
      final cw = textW(e.code, barFontSize);
      final nw = textW('${e.count}', barFontSize);
      if (cw > maxCodeW) maxCodeW = cw;
      if (nw > maxCountW) maxCountW = nw;
    }
    // chip 宽由 2:3 比例 + 圆角弧推算（桌面 531-533）
    final needLeft = (maxCodeW + 2 * padX + radius) * 5 / 2;
    final needRight = (maxCountW + 2 * padX + radius) * 5 / 3;
    final chipW = needLeft > needRight ? needLeft : needRight;
    final leftW = chipW * 2 / 5;
    final rightW = chipW - leftW;
    final gap = cell / 2;
    final barRowH = chipH + (cell / 3 > 6 ? cell / 3 : 6);
    final titleH = barRowH;

    // 换行布局
    final barAreaWidth = gridW + leftMargin + 6;
    final perRow =
        ((barAreaWidth + gap) / (chipW + gap)).floor().clamp(1, 1 << 30);
    final rows = <List<BomEntry>>[];
    for (var i = 0; i < bom.length; i += perRow) {
      rows.add(bom.sublist(i, (i + perRow).clamp(0, bom.length)));
    }

    final barTop = topMargin + gridH + 14;
    final barHeight = rows.isEmpty ? 0.0 : titleH + rows.length * barRowH;
    final totalW = (leftMargin + gridW + 8).ceil();
    final totalH = (barTop + barHeight + (cell / 2 > 10 ? cell / 2 : 10)).ceil();

    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder,
        Rect.fromLTWH(0, 0, totalW.toDouble(), totalH.toDouble()));
    // 白底
    canvas.drawRect(Rect.fromLTWH(0, 0, totalW.toDouble(), totalH.toDouble()),
        Paint()..color = const Color(0xFFFFFFFF));

    void drawText(String s, Offset center, double size, Color color,
        {FontWeight weight = FontWeight.normal}) {
      final tp = TextPainter(
        text: TextSpan(
            text: s,
            style:
                TextStyle(fontSize: size, color: color, fontWeight: weight)),
        textDirection: ui.TextDirection.ltr,
      )..layout();
      tp.paint(canvas, center - Offset(tp.width / 2, tp.height / 2));
    }

    // --- 豆格 + 每豆 code ---
    for (var y = 0; y < gh; y++) {
      for (var x = 0; x < gw; x++) {
        final i = y * gw + x;
        final code = codes[i];
        var rgb = codeRgb(code, (quantRgb[i * 3] << 16) |
            (quantRgb[i * 3 + 1] << 8) | quantRgb[i * 3 + 2]);
        final maskedOut = beadMask != null && !beadMask[i];
        if (maskedOut && solidBg != null) {
          // 纯色背景（纯白/纯黑），不淡化、不画 code
          rgb = solidBg;
        } else if (maskedOut && useFade) {
          // 淡化：c + (255-c)*maskFade
          final r = rgb.red + (255 - rgb.red) * _maskFade;
          final g = rgb.green + (255 - rgb.green) * _maskFade;
          final b = rgb.blue + (255 - rgb.blue) * _maskFade;
          rgb = Color.fromARGB(255, r.round(), g.round(), b.round());
        }
        final x1 = leftMargin + x * cell;
        final y1 = topMargin + y * cell;
        canvas.drawRect(Rect.fromLTWH(x1, y1, cell, cell), Paint()..color = rgb);
        if (maskedOut) continue;
        // 对比色 code 文字（桌面 577-588）
        final lum = 0.299 * rgb.red + 0.587 * rgb.green + 0.114 * rgb.blue;
        final tc = lum > 128 ? const Color(0xFF000000) : const Color(0xFFFFFFFF);
        drawText(code, Offset(x1 + cell / 2, y1 + cell / 2),
            (cell * 0.43).clamp(9.0, 1e9), tc);
      }
    }

    // --- 网格线（minor 浅 / major 深） ---
    final minorPaint = Paint()
      ..color = const Color(0xFFC8C8C8)
      ..strokeWidth = 1;
    final majorPaint = Paint()
      ..color = const Color(0xFF5A5A5A)
      ..strokeWidth = cell >= 16 ? 3 : 2;
    for (var xi = 0; xi <= gw; xi++) {
      final x = leftMargin + xi * cell;
      final major = xi % _majorEvery == 0;
      canvas.drawLine(Offset(x, topMargin), Offset(x, topMargin + gridH),
          major ? majorPaint : minorPaint);
    }
    for (var yi = 0; yi <= gh; yi++) {
      final y = topMargin + yi * cell;
      final major = yi % _majorEvery == 0;
      canvas.drawLine(Offset(leftMargin, y), Offset(leftMargin + gridW, y),
          major ? majorPaint : minorPaint);
    }

    // --- 坐标刻度（左 + 上，每 majorEvery） ---
    final tickColor = const Color(0xFF282828);
    final tickSize = (cell * 0.8).clamp(10.0, 1e9);
    for (var xi = _majorEvery; xi <= gw; xi += _majorEvery) {
      final x = leftMargin + xi * cell;
      drawText('$xi', Offset(x, topMargin - 10), tickSize, tickColor);
    }
    for (var yi = _majorEvery; yi <= gh; yi += _majorEvery) {
      final y = topMargin + yi * cell;
      // 左对齐到 leftMargin 内侧
      final tp = TextPainter(
        text: TextSpan(text: '$yi', style: TextStyle(fontSize: tickSize, color: tickColor)),
        textDirection: ui.TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(leftMargin - tp.width - 8, y - tp.height / 2));
    }

    // --- 底部 BOM 条 ---
    if (rows.isNotEmpty) {
      drawText('BOM', Offset(leftMargin + textW('BOM', barFontSize, weight: FontWeight.bold) / 2, barTop + 2 + barFontSize / 2), barFontSize, const Color(0xFF1E1E1E), weight: FontWeight.bold);
      var yy = barTop + titleH;
      for (final row in rows) {
        var xx = leftMargin;
        for (final e in row) {
          final rgb = codeRgb(e.code, 0x808080);
          final chipRect = Rect.fromLTWH(xx, yy, chipW, chipH);
          // 外 chip：白底圆角 + 黑边
          canvas.drawRRect(
              RRect.fromRectAndRadius(chipRect, Radius.circular(radius)),
              Paint()..color = const Color(0xFFFFFFFF));
          // 左色块（圆角左 + 方形右拼直分线）
          final leftRect = Rect.fromLTWH(xx, yy, leftW, chipH);
          canvas.save();
          canvas.clipRRect(
              RRect.fromRectAndRadius(chipRect, Radius.circular(radius)));
          canvas.drawRect(leftRect, Paint()..color = rgb);
          canvas.restore();
          // 分线
          canvas.drawLine(Offset(xx + leftW, yy + 1),
              Offset(xx + leftW, yy + chipH - 1), Paint()..color = const Color(0xFF000000)..strokeWidth = 1);
          // code（左半，对比色）
          final lum = 0.299 * rgb.red + 0.587 * rgb.green + 0.114 * rgb.blue;
          final cc = lum > 128 ? const Color(0xFF000000) : const Color(0xFFFFFFFF);
          drawText(e.code, Offset(xx + leftW / 2, yy + chipH / 2), barFontSize, cc);
          // 数量（右半，深字）
          drawText('${e.count}', Offset(xx + leftW + rightW / 2, yy + chipH / 2),
              barFontSize, const Color(0xFF141414));
          // 黑边最后画（盖在色块上）
          canvas.drawRRect(
              RRect.fromRectAndRadius(chipRect, Radius.circular(radius)),
              Paint()
                ..style = PaintingStyle.stroke
                ..strokeWidth = 1
                ..color = const Color(0xFF000000));
          xx += chipW + gap;
        }
        yy += barRowH;
      }
    }

    final picture = recorder.endRecording();
    return picture.toImage(totalW, totalH);
  }
}
