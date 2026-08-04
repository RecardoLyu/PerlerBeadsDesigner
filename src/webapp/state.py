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
        # 图纸豆子风格：real=真实豆子(圆环填色) | square=经典方格
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


# Global singleton (single-user desktop app)
STATE = AppState()
