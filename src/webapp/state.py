"""
Session state for the webapp backend.

Holds the single-user working state (image, mask, pattern, BOM) and reuses the
existing tkinter-free core modules. One AppState instance per running app.
"""
import os
import sys
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
