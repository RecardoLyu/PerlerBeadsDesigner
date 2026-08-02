import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/services.dart';

/// 导出服务：把图纸 ui.Image 编码为 PNG，经原生 MediaStore 写入相册
/// 「Pictures/拼豆图纸」文件夹（无需选目录、无需权限弹窗，Android 10+ 直接生效，
/// Android 9 及以下由原生侧写外部存储并触发媒体扫描）。
class ExportService {
  ExportService._();

  static const _channel = MethodChannel('perler_app/export');

  /// 导出分辨率档（对应原「纸张 A4/Letter」，改为按输出宽度像素）。
  /// label 展示给用户；widthPx 为目标图宽（高按图纸纵横比自适应）。
  static const resolutions = <(String, int)>[
    ('1080P', 1080),
    ('2K', 2560),
    ('4K', 3840),
  ];

  /// 把图纸 [chart] 编码为 PNG 并保存到相册，返回保存结果描述。
  /// [targetWidthPx] 目标宽度像素；按图纸纵横比缩放（锐利图纸用最近邻放大防糊）。
  static Future<String> saveChart(ui.Image chart, int targetWidthPx,
      {String? name}) async {
    final scale = targetWidthPx / chart.width;
    final targetH = (chart.height * scale).round();
    final fileName =
        '${name ?? 'pattern'}_${DateTime.now().millisecondsSinceEpoch}.png';

    Uint8List png;
    ui.Image? scaled;
    try {
      if ((scale - 1.0).abs() < 1e-3) {
        png = await _encodePng(chart);
      } else {
        // 离屏缩放到目标分辨率（图纸是锐利豆块，放大用低保真避免边缘发虚）
        final recorder = ui.PictureRecorder();
        final canvas = ui.Canvas(recorder);
        canvas.drawImageRect(
          chart,
          ui.Rect.fromLTWH(0, 0, chart.width.toDouble(), chart.height.toDouble()),
          ui.Rect.fromLTWH(0, 0, targetWidthPx.toDouble(), targetH.toDouble()),
          ui.Paint()..filterQuality = ui.FilterQuality.none,
        );
        scaled = await recorder
            .endRecording()
            .toImage(targetWidthPx, targetH);
        png = await _encodePng(scaled);
      }
    } finally {
      scaled?.dispose();
    }

    final rel = await _channel.invokeMethod<String>('savePng', {
      'bytes': png,
      'name': fileName,
    });
    return rel ?? fileName;
  }

  static Future<Uint8List> _encodePng(ui.Image img) async {
    final bd = await img.toByteData(format: ui.ImageByteFormat.png);
    if (bd == null) throw StateError('图纸 PNG 编码失败');
    return bd.buffer.asUint8List();
  }
}
