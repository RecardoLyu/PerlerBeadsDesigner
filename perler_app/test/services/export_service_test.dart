import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/services/export_service.dart';

void main() {
  group('双风格 PNG 导出', () {
    test('默认图纸，可单选真实或同时导出两种', () {
      expect(ExportService.stylesForSelection(0), ['real']);
      expect(ExportService.stylesForSelection(1), ['square']);
      expect(ExportService.stylesForSelection(2), ['real', 'square']);
    });

    test('单风格保留文件名，双风格添加后缀', () {
      expect(ExportService.fileBaseName('pattern', 'square', 1), 'pattern');
      expect(ExportService.fileBaseName('pattern', 'real', 2), 'pattern_real');
      expect(ExportService.fileBaseName('pattern', 'square', 2), 'pattern_chart');
    });
  });
}
