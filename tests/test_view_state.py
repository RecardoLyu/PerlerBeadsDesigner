"""
视图状态 + 全局手势的静态断言测试（读前端源码做正则校验，防回归；不依赖浏览器）。

覆盖本轮改动（N6 视图状态 / N7 全局中键平移 / N1 导出精简）：
- 「换图必换模式」：crop.js / app.js 的改图入口附近必须调用 setOriginalView()。
- setOriginalView 必须挂到 window（供 crop.js / app.js 跨模块调用）。
- 全局中键=平移：scribble.js / segment.js / crop.js 的画布 mousedown 必须有
  `e.button !== 0` 守卫（只认左键，中/右键放行给 viewer 平移）。
- 导出精简：app.py 的 ExportReq 不再含 paper/export_pdf/export_png 字段；
  /api/export 不再调用 export_pdf。
"""
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')
JS = os.path.join(ROOT, 'src', 'webapp', 'static', 'js')
APP_PY = os.path.join(ROOT, 'src', 'webapp', 'app.py')


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


class TestOriginalViewHook(unittest.TestCase):
    """setOriginalView 挂到 window + 各改图入口调用它。"""

    def test_setOriginalView_exposed_on_window(self):
        seg = _read(os.path.join(JS, 'segment.js'))
        self.assertIn('window.setOriginalView = setOriginalView', seg)

    def test_crop_enter_switches_to_original(self):
        crop = _read(os.path.join(JS, 'crop.js'))
        m = re.search(r'function enter\(\)\s*\{(.*?)\n  \}', crop, re.S)
        self.assertIsNotNone(m, 'crop.js 应有 enter()')
        self.assertIn('setOriginalView()', m.group(1), '进入裁剪必须先切回原图模式')

    def test_crop_apply_switches_to_original(self):
        crop = _read(os.path.join(JS, 'crop.js'))
        m = re.search(r"cropApplyBtn'\)\.addEventListener\('click'(.*?)\n  \}\);", crop, re.S)
        self.assertIsNotNone(m, 'crop.js 应有 cropApplyBtn 监听')
        self.assertIn('setOriginalView()', m.group(1), '裁剪应用后必须切回原图模式')

    def test_app_image_changing_entries_switch_to_original(self):
        app = _read(os.path.join(JS, 'app.js'))
        # 加载 / 基本调整 / 恢复原图 三处都调用 setOriginalView
        self.assertGreaterEqual(app.count('setOriginalView()'), 3,
                                'app.js 的加载/调整/恢复入口都应调用 setOriginalView()')


class TestGlobalMiddleMousePan(unittest.TestCase):
    """画布 mousedown 只认左键（e.button !== 0 守卫），中键放行平移。"""

    def _assert_left_button_guard(self, fname):
        src = _read(os.path.join(JS, fname))
        # 文件内应含 e.button !== 0 守卫
        self.assertIn('e.button !== 0', src,
                      f'{fname} 的 mousedown 应有 e.button !== 0 守卫（全局中键=平移）')

    def test_scribble_left_only(self):
        self._assert_left_button_guard('scribble.js')

    def test_segment_box_select_left_only(self):
        self._assert_left_button_guard('segment.js')

    def test_crop_left_only(self):
        self._assert_left_button_guard('crop.js')


class TestExportPngOnly(unittest.TestCase):
    """桌面端导出只留 PNG、去掉纸张/PDF 字段与调用。"""

    def test_export_req_no_paper_pdf_fields(self):
        src = _read(APP_PY)
        m = re.search(r'class ExportReq\(BaseModel\):(.*?)\n\n', src, re.S)
        self.assertIsNotNone(m, 'app.py 应有 ExportReq')
        body = m.group(1)
        for field in ('paper', 'export_pdf', 'export_png'):
            self.assertNotIn(field, body, f'ExportReq 不应再含 {field} 字段')

    def test_export_route_never_calls_export_pdf(self):
        src = _read(APP_PY)
        m = re.search(r'@app\.post\("/api/export"\)(.*?return \{"ok")', src, re.S)
        self.assertIsNotNone(m, 'app.py 应有 /api/export 路由')
        self.assertNotIn('export_pdf', m.group(1), '/api/export 不应再调用 export_pdf')


if __name__ == '__main__':
    unittest.main()
