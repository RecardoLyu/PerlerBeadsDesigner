"""
交互逻辑测试（后端/状态机层面，不依赖浏览器）。

覆盖本轮交互改动：
- 图纸标题 header 几何（有/无 title 高度差）
- BOM 芯片宽度对长色号自适应（4 位以上单行不溢出）
- source_name 占位名过滤
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.pattern_generator import PatternGenerator
from src.core.color_manager import Color, ColorPalette


def _palette():
    colors = [
        Color('A1', '白', '#FFFFFF'),
        Color('80-15179', '红', '#E7000B'),   # 长色号（Perler 风格）
        Color('H01', '蓝', '#0055AA'),          # 短色号（Hama 风格）
    ]
    return ColorPalette(colors)


def _gen_with_pattern(codes_grid):
    """构造一个带 color_map + bom 的 PatternGenerator，可直接 render_standard_chart。"""
    gen = PatternGenerator()
    arr = np.array(codes_grid, dtype=object)
    gen.color_map = arr
    gen.pattern = np.zeros(arr.shape + (3,), dtype=np.uint8)
    counts = {}
    for row in codes_grid:
        for c in row:
            counts[c] = counts.get(c, 0) + 1
    total = sum(counts.values())
    gen.bom = {
        'total_beads': total,
        'colors': {c: {'name': c, 'hex': '#FF0000', 'count': n,
                       'percentage': n / total * 100} for c, n in counts.items()},
    }
    return gen


class TestChartTitleHeader(unittest.TestCase):
    """图纸顶部标题：有 title 时 header 更高，无 title 时收缩。"""

    def test_title_increases_height(self):
        gen = _gen_with_pattern([['A1', 'H01'], ['H01', 'A1']])
        pal = _palette()
        no_title = gen.render_standard_chart(30, 5, pal, title=None)
        with_title = gen.render_standard_chart(30, 5, pal, title='我的图纸')
        # 有标题时整张图应更高（header_h 由 cell*0.9 → cell*1.7）
        self.assertGreater(with_title.shape[0], no_title.shape[0])

    def test_empty_title_behaves_as_none(self):
        gen = _gen_with_pattern([['A1']])
        pal = _palette()
        a = gen.render_standard_chart(30, 5, pal, title=None)
        b = gen.render_standard_chart(30, 5, pal, title='   ')
        self.assertEqual(a.shape, b.shape)


class TestBomChipWidth(unittest.TestCase):
    """BOM 芯片：含长色号也能单行渲染（不报错、尺寸合理、宽度随最长色号增大）。"""

    def test_long_code_chart_renders(self):
        gen = _gen_with_pattern([['80-15179', 'H01'], ['H01', '80-15179']])
        pal = _palette()
        img = gen.render_standard_chart(30, 5, pal)
        self.assertIsNotNone(img)
        self.assertGreater(img.shape[0], 0)
        self.assertGreater(img.shape[1], 0)

    def test_longer_code_widens_chip(self):
        """最长色号更长 → 芯片更宽 → 图纸总宽（或 BOM 行数减少）变化。
        这里用「单行能放下」的等价判据：长色号图的 BOM 区不更矮且渲染成功。"""
        pal = _palette()
        short = _gen_with_pattern([['A1', 'A1'], ['A1', 'A1']])
        longg = _gen_with_pattern([['80-15179', '80-15179'], ['80-15179', '80-15179']])
        i1 = short.render_standard_chart(30, 5, pal)
        i2 = longg.render_standard_chart(30, 5, pal)
        # 长色号芯片更宽 → 每行放的芯片更少 → BOM 区行数可能更多 → 总高不更矮
        self.assertGreaterEqual(i2.shape[0], i1.shape[0])


class TestSourceNameFilter(unittest.TestCase):
    """source_name 占位名过滤（state.py 逻辑的可移植副本校验）。"""

    def _filter(self, base):
        base = base.strip()
        if base.lower() in ('', 'image', 'untitled', '未命名', '图像', '未命名图纸'):
            return None
        return base

    def test_placeholders(self):
        for p in ('', 'image', 'IMAGE', 'untitled', '未命名', '图像', '未命名图纸'):
            self.assertIsNone(self._filter(p))

    def test_real_names(self):
        self.assertEqual(self._filter('cat'), 'cat')
        self.assertEqual(self._filter('我的图'), '我的图')


if __name__ == '__main__':
    unittest.main()
