"""
Session state for the webapp backend.

Holds the single-user working state (image, mask, pattern, BOM) and reuses the
existing tkinter-free core modules. One AppState instance per running app.
"""
import os
import sys
import json
import threading
from typing import Optional

import numpy as np

from src.core.image_processor import ImageProcessor
from src.core.color_manager import ColorManager
from src.core.pattern_generator import PatternGenerator, PatternConfig
from src.utils.segmentation import IterativeGrabCutState


def _resource_path(*parts) -> str:
    """Resolve a bundled resource path (dev + PyInstaller onedir)."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    candidate = os.path.join(root, *parts)
    if os.path.exists(candidate):
        return candidate
    base = getattr(sys, '_MEIPASS', root)
    return os.path.join(base, *parts)


class AppState:
    """Central working state. All mutation goes through the lock."""

    def __init__(self):
        self.lock = threading.RLock()
        self.processor = ImageProcessor()
        colors_file = _resource_path('src', 'assets', 'colors_221.json')
        self.color_manager = ColorManager(colors_file=colors_file)
        self.generator = PatternGenerator()
        self.segmentation: Optional[IterativeGrabCutState] = None
        self.mask: Optional[np.ndarray] = None        # uint8 binary (0/255)
        self.bead_mask: Optional[np.ndarray] = None   # bool (h_beads, w_beads)
        self.mask_undo: list = []                     # mask 历史（撤销），cap 3
        self.mask_redo: list = []                     # mask 历史（重做），cap 3
        self.output_dir: str = os.path.abspath("output")
        self.grid_width: int = 104  # 图纸宽（豆），分割下采样目标据此算；生成图纸时同步

        # ---- 图纸画板（board）----
        self.board_active: bool = False
        self.board_size: int = 0                       # 网格边长（豆），52 | 104
        self.board_brand: str = 'mard'                 # 画板用色品牌（独立于图像转换）
        # 网格：object 数组 (h,w)，每格色号 str 或 None（空板格）
        self.board_grid: Optional[np.ndarray] = None
        # 底图：用户裁剪好的正方形 RGB 图（叠加显示在绘制层之下）
        self.board_base: Optional[np.ndarray] = None   # (N,N,3) uint8 正方形
        self.board_base_src: Optional[np.ndarray] = None  # 导入的底图原图（待裁剪）
        self.board_base_opacity: float = 0.35
        self.board_base_visible: bool = True
        # 增量笔画历史（撤销/重做，各 cap 5）。每条 op={'kind','cells':[(x,y,old,new),...]}
        self.board_undo: list = []
        self.board_redo: list = []

    # ---- 用户偏好（默认参数），持久化到安装目录 settings.json ----
    # 默认值以手机端 AppSettings 为基准，统一三处（HTML/state.py/Flutter）不一致。
    DEFAULT_SETTINGS: dict = {
        # 图纸默认参数
        "width": 104, "keepRatio": True, "maxColors": 0, "salience": 1.0,
        "metric": "ciede2000", "dither": False, "ditherStrength": 1.0,
        "icm": False, "icmSmooth": 0.5, "brand": "mard", "maskBg": "none",
        # 分割默认参数
        "segMethod": "watershed", "brushSize": 12,
        # 外观
        "theme": "system",
        # 图片换肤（skinImage 非空即启用；skinColor 主色、skinAccent 辅助色 hex 或空串；
        # skinOpacity 亮暗共用单一不透明度；skinBlur 模糊档 0=无/1=中/2=高）
        "skinImage": "", "skinColor": "", "skinAccent": "",
        "skinOpacity": 0.15, "skinBlur": 1,
        # 图纸豆子风格：real=真实风(同心圆环+中央孔洞) | square=图纸风
        "beadStyle": "real",
    }

    @staticmethod
    def _install_dir() -> str:
        """安装目录：打包后是 exe 同级目录，源码运行是项目根。"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

    def _settings_path(self) -> str:
        return os.path.join(self._install_dir(), 'settings.json')

    def load_settings(self) -> dict:
        """读 settings.json（缺字段回落到内置默认）；文件不存在/损坏返回默认。"""
        s = dict(self.DEFAULT_SETTINGS)
        try:
            with open(self._settings_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                s.update({k: v for k, v in data.items() if k in s})
        except (OSError, ValueError):
            pass
        return s

    def save_settings(self, new: dict):
        """把（白名单过滤后的）设置写回 settings.json。"""
        cur = self.load_settings()
        cur.update({k: v for k, v in (new or {}).items() if k in self.DEFAULT_SETTINGS})
        try:
            with open(self._settings_path(), 'w', encoding='utf-8') as f:
                json.dump(cur, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ---- 源图片文件名（图纸顶部标题用）----
    @property
    def source_name(self) -> Optional[str]:
        """当前图像的文件名（去路径去扩展名）；占位名返回 None（不渲染图纸标题）。
        裁剪/调整不清除（仍是同一张源图），重新加载才覆盖。"""
        p = getattr(self.processor, 'image_path', None)
        if not p:
            return None
        base = os.path.splitext(os.path.basename(p))[0].strip()
        # 占位名不显示标题
        if base.lower() in ('', 'image', 'untitled', '未命名', '图像', '未命名图纸'):
            return None
        return base

    # ---- image ----
    def has_image(self) -> bool:
        return self.processor.current_image is not None

    def require_image(self) -> np.ndarray:
        img = self.processor.current_image
        if img is None:
            raise ValueError("尚未加载图像")
        return img

    def set_mask(self, mask: Optional[np.ndarray]):
        with self.lock:
            self.mask = None if mask is None else mask.copy()

    # ---- mask 形态学历史（撤销/重做，各保留 3 步） ----
    def push_mask_history(self):
        """Before a morph op: snapshot current mask onto undo stack, clear redo."""
        with self.lock:
            if self.mask is not None:
                self.mask_undo.append(self.mask.copy())
                self.mask_undo = self.mask_undo[-3:]
            self.mask_redo = []

    def undo_mask(self) -> bool:
        """Pop undo -> current becomes redo. Returns True if state changed."""
        with self.lock:
            if not self.mask_undo:
                return False
            if self.mask is not None:
                self.mask_redo.append(self.mask.copy())
                self.mask_redo = self.mask_redo[-3:]
            self.mask = self.mask_undo.pop()
            return True

    def redo_mask(self) -> bool:
        """Pop redo -> current becomes undo. Returns True if state changed."""
        with self.lock:
            if not self.mask_redo:
                return False
            if self.mask is not None:
                self.mask_undo.append(self.mask.copy())
                self.mask_undo = self.mask_undo[-3:]
            self.mask = self.mask_redo.pop()
            return True

    def new_grabcut_session(self) -> IterativeGrabCutState:
        """Start a fresh iterative GrabCut session on the current image.

        GrabCut 在压缩工作图（4×图纸宽）上跑以提速，返回 mask 仍为原图尺寸。
        """
        with self.lock:
            self.segmentation = IterativeGrabCutState(
                self.require_image(), grid_w=self.grid_width)
            return self.segmentation

    def get_grabcut_session(self) -> IterativeGrabCutState:
        if self.segmentation is None:
            self.new_grabcut_session()
        return self.segmentation

    # ================= 图纸画板 board =================
    def board_new(self, size: int, brand: str):
        """新建 size×size 空画板（清底图与历史）。"""
        with self.lock:
            self.board_size = int(size)
            self.board_brand = brand
            self.board_grid = np.full((size, size), None, dtype=object)
            self.board_base = None
            self.board_base_src = None
            self.board_undo, self.board_redo = [], []
            self.board_active = True

    def _board_palette(self):
        """画板品牌独立加载色板（不污染图像转换的 color_manager.brand）。"""
        from src.core.color_manager import ColorPalette
        cm = self.color_manager
        _, fname = cm.BRANDS[self.board_brand]
        return ColorPalette.load_from_json(os.path.join(cm.palette_dir, fname))

    def board_apply_op(self, op: dict):
        """应用一个增量 op 到网格并压入撤销栈（清空重做栈，cap 5）。
        op['cells'] = [(x, y, old, new), ...]，old/new 为色号 str 或 None。"""
        with self.lock:
            if self.board_grid is None:
                return
            for x, y, _old, new in op['cells']:
                self.board_grid[y, x] = new
            self.board_undo.append(op)
            self.board_undo = self.board_undo[-5:]
            self.board_redo = []

    def board_undo_op(self) -> bool:
        """撤销：写回每格 old 值。返回是否有改动。"""
        with self.lock:
            if not self.board_undo:
                return False
            op = self.board_undo.pop()
            for x, y, old, _new in op['cells']:
                self.board_grid[y, x] = old
            self.board_redo.append(op)
            self.board_redo = self.board_redo[-5:]
            return True

    def board_redo_op(self) -> bool:
        """重做：重放每格 new 值。返回是否有改动。"""
        with self.lock:
            if not self.board_redo:
                return False
            op = self.board_redo.pop()
            for x, y, _old, new in op['cells']:
                self.board_grid[y, x] = new
            self.board_undo.append(op)
            self.board_undo = self.board_undo[-5:]
            return True

    def board_to_generator(self):
        """把画板网格灌进 generator，使 render_standard_chart/BOM 直接可用。

        空格映射为占位码 '__empty__' + bead_mask=False：render_standard_chart
        对 masked-out 格 continue 跳过（真实风空板格不画豆只留网格线），
        BOM 由 rebuild_bom_with_mask 只统计有豆格（空格不计入）。
        """
        gen = self.generator
        palette = self._board_palette()
        g = self.board_grid
        h, w = g.shape
        pat = np.zeros((h, w, 3), dtype=np.uint8)
        pat[:] = (245, 243, 238)                    # 空格 = 底板色 PEGBOARD
        cmap = np.empty((h, w), dtype=object)
        bead_mask = np.zeros((h, w), dtype=bool)
        for y in range(h):
            for x in range(w):
                code = g[y, x] or None
                bead_mask[y, x] = bool(code)
                cmap[y, x] = code if code else '__empty__'
                if code:
                    c = palette.get_color(code)
                    pat[y, x] = c.rgb if c else (128, 128, 128)
        gen.pattern = pat
        gen.color_map = cmap
        gen.bead_mask = bead_mask
        gen.rebuild_bom_with_mask(bead_mask, palette)


# Global singleton (single-user desktop app)
STATE = AppState()
