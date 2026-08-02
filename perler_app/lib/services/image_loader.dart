import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';

/// 图像加载服务：从相册/文件系统选图并解码为 RGB 字节（h*w*3）。
/// 解码用 Flutter 引擎的 instantiateImageCodec（Skia），解码能力远强于纯 Dart
/// 的 image 包，几乎能解任何 PNG/JPG/BMP/WEBP（含 16bit、interlace、调色板等）。
class ImageLoader {
  ImageLoader._();

  /// 解码结果为 RGB 字节 + 尺寸 + 文件名
  static Future<({Uint8List rgb, int width, int height, String name})?> _decode(
      Uint8List bytes, String name) async {
    // 用 Flutter 引擎解码（Skia），最稳
    final codec = await ui.instantiateImageCodec(bytes);
    final frame = await codec.getNextFrame();
    final image = frame.image;
    final w = image.width, h = image.height;
    // 读回 RGBA 字节
    final byteData = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    if (byteData == null) {
      image.dispose();
      return null;
    }
    final rgba = byteData.buffer.asUint8List();
    // RGBA → RGB（alpha 合成到白底，避免透明边缘发黑）
    final rgb = Uint8List(w * h * 3);
    for (var s = 0, d = 0; d < w * h * 3; s += 4, d += 3) {
      final a = rgba[s + 3];
      if (a >= 255) {
        rgb[d] = rgba[s];
        rgb[d + 1] = rgba[s + 1];
        rgb[d + 2] = rgba[s + 2];
      } else {
        final af = a / 255.0;
        rgb[d] = (rgba[s] * af + 255 * (1 - af)).round();
        rgb[d + 1] = (rgba[s + 1] * af + 255 * (1 - af)).round();
        rgb[d + 2] = (rgba[s + 2] * af + 255 * (1 - af)).round();
      }
    }
    image.dispose();
    return (rgb: rgb, width: w, height: h, name: name);
  }

  /// 从相册选图
  static Future<({Uint8List rgb, int width, int height, String name})?> pickFromGallery() async {
    try {
      final picker = ImagePicker();
      final x = await picker.pickImage(source: ImageSource.gallery);
      if (x == null) return null;
      final bytes = await x.readAsBytes();
      return await _decode(bytes, x.name);
    } catch (_) {
      return null;
    }
  }

  /// 从文件系统选图（支持更多格式）
  static Future<({Uint8List rgb, int width, int height, String name})?> pickFromFile() async {
    try {
      final res = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['jpg', 'jpeg', 'png', 'bmp', 'webp'],
        withData: true,
      );
      if (res == null || res.files.isEmpty) return null;
      final f = res.files.first;
      // file_picker 在 Android 上 withData 可能拿不到 bytes，需回退到读 path
      Uint8List? bytes = f.bytes;
      if (bytes == null && f.path != null) {
        bytes = await _readPath(f.path!);
      }
      if (bytes == null) return null;
      return await _decode(bytes, f.name);
    } catch (_) {
      return null;
    }
  }

  static Future<Uint8List?> _readPath(String path) async {
    try {
      final x = XFile(path);
      return await x.readAsBytes();
    } catch (_) {
      return null;
    }
  }
}
