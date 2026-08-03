import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/state/app_state.dart';

/// 交互逻辑纯函数测试：文件名标题派生（占位名过滤）。
void main() {
  group('deriveSourceTitle 占位名过滤', () {
    test('正常文件名去扩展名', () {
      expect(deriveSourceTitle('cat.png'), 'cat');
      expect(deriveSourceTitle('我的图.jpg'), '我的图');
      expect(deriveSourceTitle('a.b.c.png'), 'a.b.c');
    });

    test('去路径只留文件名', () {
      expect(deriveSourceTitle('D:/photos/flower.webp'), 'flower');
      expect(deriveSourceTitle('C:\\Users\\x\\star.png'), 'star');
    });

    test('占位名返回 null', () {
      for (final p in ['', 'image', 'untitled', '未命名', '图像', '未命名图纸', 'IMAGE', 'Untitled']) {
        expect(deriveSourceTitle(p), isNull, reason: '占位名应过滤: $p');
      }
    });

    test('占位名带扩展名也过滤', () {
      expect(deriveSourceTitle('图像.png'), isNull);
      expect(deriveSourceTitle('image.jpg'), isNull);
    });

    test('前后空白被 trim', () {
      expect(deriveSourceTitle('  cat  .png'), 'cat');
    });
  });
}
