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

  /// 拼豆底板色：浅米白，中央孔洞透出的是底板而不是纯黑阴影（对应桌面 PEGBOARD）。
  static const Color _pegboard = Color(0xFFF5F3EE);

  /// 画一颗豆子（对应桌面 _draw_bead）。real=真实拼豆（同心圆环 + 中央孔洞透出
  /// 底板色）；square=经典实心方格。
  static void _drawBead(Canvas canvas, double x1, double y1, double cell,
      Color rgb, String style) {
    if (style != 'real') {
      canvas.drawRect(Rect.fromLTWH(x1, y1, cell, cell), Paint()..color = rgb);
      return;
    }
    final cx = x1 + cell / 2, cy = y1 + cell / 2;
    final r = cell * 0.46;
    Color scale(double f) => Color.fromARGB(255, (rgb.red * f).round(),
        (rgb.green * f).round(), (rgb.blue * f).round());
    // 1) 外圈描边（压暗一档）做立体边缘
    canvas.drawCircle(Offset(cx, cy), r, Paint()..color = scale(0.72));
    // 2) 豆体圆盘：向内一圈填豆色
    canvas.drawCircle(Offset(cx, cy), r * 0.82, Paint()..color = rgb);
    // 3) 中央孔洞外缘：压暗的豆色细环，模拟穿孔内壁阴影（孔径 ≈ 0.26 cell）
    final hr = cell * 0.13;
    canvas.drawCircle(Offset(cx, cy), hr, Paint()..color = scale(0.55));
    // 4) 孔洞本身：透出拼豆底板色（浅米白），不是黑色阴影
    canvas.drawCircle(Offset(cx, cy), hr * 0.72, Paint()..color = _pegboard);
  }

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
    String? title,          // 图纸顶部文件名（占位名传 null 不画）
    String? brand,          // 品牌标签（左上角信息行）
    int colorCount = 0,     // 用到的颜色数
    int totalBeads = 0,     // 总豆数
    String beadStyle = 'real', // real=真实豆子(同心圆环+中央孔洞) | square=经典方格
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
    // 顶部 header 区：文件名（居中、粗体）+ 左上角品牌信息。无标题也留一行放品牌信息。
    final hasTitle = title != null && title.trim().isNotEmpty;
    final headerH = hasTitle ? cell * 1.7 : cell * 0.9;
    final topMargin = headerH + cell + 10;   // header + 顶部刻度数字
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
    // 左色块装 code、右块装 count，各自独立按最长文本定宽，
    // 保证任意长度色号（如 Perler 80-15179）单行不溢出。
    final leftW = maxCodeW + 2 * padX + radius;
    final rightW = maxCountW + 2 * padX + radius;
    final chipW = leftW + rightW;
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

    // --- header：文件名（顶部正中，粗体）+ 左上角品牌信息 ---
    if (hasTitle) {
      drawText(title!, Offset(totalW / 2, headerH / 2),
          (cell * 1.2).clamp(12.0, 1e9), const Color(0xFF141414),
          weight: FontWeight.w700);
    }
    if (brand != null && brand.isNotEmpty) {
      // 品牌信息紧凑单行：品牌 · N色 · 共M豆（常规体，颜色与刻度一致）
      final info = '$brand · $colorCount 色 · 共 $totalBeads 豆';
      final infoSize = (cell * 0.6).clamp(9.0, 1e9);
      final iy = hasTitle
          ? headerH - infoSize / 2 - (cell / 8 > 2 ? cell / 8 : 2)
          : headerH / 2;
      final tp = TextPainter(
        text: TextSpan(
            text: info,
            style: TextStyle(fontSize: infoSize, color: const Color(0xFF282828))),
        textDirection: ui.TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(leftMargin, iy - tp.height / 2));
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
        _drawBead(canvas, x1, y1, cell, rgb, beadStyle);
        if (maskedOut) continue;
        // 真实豆子风格豆内不印色号，色号/数量统一由图纸外 BOM 呈现
        if (beadStyle == 'real') continue;
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
