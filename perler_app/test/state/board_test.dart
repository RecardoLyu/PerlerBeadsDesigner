import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/algo/quantizer.dart';
import 'package:perler_app/state/app_state.dart';

/// 画板状态/逻辑测试：新建/笔画/填充/框选/撤销重做/清空/BOM。
/// 不依赖 rootBundle：直接注入极简调色板构造 BoardState。
Palette _tinyPalette() => Palette([
      BeadColor('R', '红', '#FF0000'),
      BeadColor('G', '绿', '#00FF00'),
      BeadColor('B', '蓝', '#0000FF'),
    ], metric: 'weighted');

/// 测试专用 Notifier：跳过 assets 加载，直接用注入的 palette 建板。
class _TestBoardNotifier extends BoardNotifier {
  _TestBoardNotifier(super.ref, this._palette);
  final Palette _palette;
  @override
  Future<void> newBoard(int size, String brand) async {
    state = BoardState(
      size: size,
      brand: brand,
      grid: List<String?>.filled(size * size, null),
      palette: _palette,
      color: 'R',
    );
  }
}

ProviderContainer _mk(Palette p) => ProviderContainer(overrides: [
      boardProvider.overrideWith((ref) => _TestBoardNotifier(ref, p)),
    ]);

void main() {
  group('BoardNotifier', () {
    test('新建画板：网格全空、色号默认', () async {
      final c = _mk(_tinyPalette());
      await c.read(boardProvider.notifier).newBoard(4, 'mard');
      final b = c.read(boardProvider);
      expect(b.grid.length, 16);
      expect(b.grid.every((e) => e == null), true);
      expect(b.color, 'R');
    });

    test('笔画写入 + BOM 只统计有豆格', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.stroke({0, 1, 5}, 'R'); // (0,0)(1,0)(1,1)
      final b = c.read(boardProvider);
      expect(b.grid[0], 'R');
      expect(b.grid[1], 'R');
      expect(b.grid[5], 'R');
      expect(n.totalBeads, 3);
      final bom = n.bom();
      expect(bom.length, 1);
      expect(bom.first.code, 'R');
      expect(bom.first.count, 3);
    });

    test('橡皮擦除（code=null）', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.stroke({0, 1}, 'R');
      n.stroke({0}, null);
      expect(c.read(boardProvider).grid[0], null);
      expect(c.read(boardProvider).grid[1], 'R');
    });

    test('油漆桶 flood fill 整板', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.fill(1, 1, 'G'); // 全空板 → 填满 16
      expect(c.read(boardProvider).grid.every((e) => e == 'G'), true);
      // 已同色再填 → 0 改动（撤销栈不增）
      final undoLen = c.read(boardProvider).undo.length;
      n.fill(1, 1, 'G');
      expect(c.read(boardProvider).undo.length, undoLen);
    });

    test('框选填充矩形', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.rectFill(1, 1, 2, 2, 'B'); // 2×2 中心
      final g = c.read(boardProvider).grid;
      expect(g[5], 'B'); g[6]; g[9]; g[10];
      expect(g[5], 'B'); expect(g[6], 'B'); expect(g[9], 'B'); expect(g[10], 'B');
      expect(g[0], null);
      expect(n.totalBeads, 4);
    });

    test('撤销/重做恢复网格', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.stroke({0}, 'R');
      n.stroke({1}, 'G');
      n.undoOp();
      expect(c.read(boardProvider).grid[0], 'R');
      expect(c.read(boardProvider).grid[1], null);
      expect(c.read(boardProvider).canRedo, true);
      n.redoOp();
      expect(c.read(boardProvider).grid[1], 'G');
    });

    test('撤销栈 cap 5', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      for (var i = 0; i < 8; i++) {
        n.stroke({i}, 'R');
      }
      var undos = 0;
      while (c.read(boardProvider).canUndo) {
        n.undoOp();
        undos++;
      }
      expect(undos, 5);
    });

    test('清空画板可撤销', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.stroke({0, 1, 2}, 'R');
      n.clearBoard();
      expect(n.totalBeads, 0);
      n.undoOp();
      expect(n.totalBeads, 3);
    });

    test('笔触覆盖 stampCells（brush=2 中心扩散）', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.setBrush(2);
      final cells = n.stampCells(1, 1);
      // 2×2 见方：(0,0)(1,0)(0,1)(1,1) → index 0,1,4,5
      expect(cells, {0, 1, 4, 5});
    });

    test('BOM 多色统计与排序', () async {
      final c = _mk(_tinyPalette());
      final n = c.read(boardProvider.notifier);
      await n.newBoard(4, 'mard');
      n.stroke({0, 1, 2}, 'R');
      n.stroke({5, 6}, 'G');
      n.stroke({10}, 'B');
      final bom = n.bom();
      expect(bom.length, 3);
      expect(bom[0].code, 'R'); // count desc
      expect(bom[0].count, 3);
      expect(bom[1].count, 2);
      expect(bom[2].count, 1);
      expect(n.totalBeads, 6);
    });
  });
}
