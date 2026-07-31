"""
Main GUI window for Perler Beads Designer - Tkinter Version
"""
import sys
import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import threading

# Add to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.image_processor import ImageProcessor
from src.core.color_manager import ColorManager
from src.core.pattern_generator import PatternGenerator, PatternConfig, CHART_BEAD_PX
from src.utils.segmentation import ImageSegmentation
from src.utils.export import PatternExporter
from src.ui.tooltip import attach_tooltip

# Bead cell size used for the standard-chart / grid previews and exports.
# Matches pattern_generator.CHART_BEAD_PX so preview and export stay consistent.
CHART_BEAD_SIZE = CHART_BEAD_PX
# Note: remote web scraper disabled to prefer local colors.json

# Threshold for "非白即前景" mask reconciliation. The masked-out background is
# baked to pure white (255), so a bead cell whose quantized color has any channel
# below this is real (non-background) and must be treated as foreground. 245 keeps
# near-white foreground beads (light yellow/pink) from being misread as background.
MASK_WHITE_THRESHOLD = 245


def _resource_path(*parts) -> str:
    """Resolve a bundled resource path that works both in dev and when frozen
    by PyInstaller.

    In dev the project root is two levels up from this file. In a frozen
    (onedir) build PyInstaller unpacks `datas` under `sys._MEIPASS`, and this
    file lives at `_MEIPASS/src/ui/main_window.py`, so walking up two levels
    from __file__ already lands on the bundle root that contains `src/assets`.
    We therefore try the __file__-relative location first and fall back to
    `sys._MEIPASS` for safety.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))           # project / bundle root
    candidate = os.path.join(root, *parts)
    if os.path.exists(candidate):
        return candidate
    base = getattr(sys, '_MEIPASS', root)
    return os.path.join(base, *parts)


class InteractiveImageDisplay(tk.Frame):
    """Interactive image display with accumulated foreground selection and undo support"""
    
    def __init__(self, parent, mode='view', on_selection_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.image = None
        self.photo = None
        self.mode = mode  # 'view', 'rect', 'ellipse', 'brush', 'curve', 'crop'
        self.on_selection_callback = on_selection_callback
        
        # Foreground accumulation
        self.accumulated_mask = None  # Accumulated foreground from all strokes
        self.stroke_history = []  # Stack of masks for undo
        
        # Current selection state
        self.is_selecting = False
        self.start_point = None
        self.current_path = []  # For curve/brush strokes
        self.preview_mask = None  # For preview during drawing

        # Crop state
        self.crop_rect = None  # (x1, y1, x2, y2) in image coords
        self.crop_finished = False
        
        # Display parameters
        self.brush_width = 15
        self.label = tk.Label(self, bg="white", relief="solid", borderwidth=1, cursor="crosshair")
        self.label.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Coordinate mapping (will be updated on display)
        self.display_rect = None  # (x0, y0, width, height) of actual image display
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.last_width = -1
        self.last_height = -1

        # Zoom / pan (active in 'view' mode)
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._pan_start = None
        self._minimap_photo = None
        self._pan_redraw_after = None

        # Bind mouse events
        self.label.bind("<Button-1>", self._on_mouse_press)
        self.label.bind("<B1-Motion>", self._on_mouse_drag)
        self.label.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.label.bind("<Motion>", self._on_mouse_move)
        # Zoom (Ctrl+wheel / Ctrl +/-)
        self.label.bind("<Control-MouseWheel>", self._on_zoom_wheel, add="+")
        self.label.bind("<Control-plus>", self._on_zoom_key, add="+")
        self.label.bind("<Control-equal>", self._on_zoom_key, add="+")
        self.label.bind("<Control-minus>", self._on_zoom_key, add="+")
        self.label.bind("<Control-KP_Add>", self._on_zoom_key, add="+")
        self.label.bind("<Control-KP_Subtract>", self._on_zoom_key, add="+")
        # Middle-drag pan
        self.label.bind("<Button-2>", self._on_pan_press, add="+")
        self.label.bind("<B2-Motion>", self._on_pan_move, add="+")
        self.label.bind("<ButtonRelease-2>", self._on_pan_release, add="+")
        self.label.bind("<Enter>", lambda e: self.label.focus_set(), add="+")

        # Bind Configure event to handle resize
        self.bind("<Configure>", self._on_frame_configure)

        # Don't let the pasted image resize this frame (keeps window stable).
        self.pack_propagate(False)

    def _on_zoom_wheel(self, event):
        """Ctrl + mouse wheel zoom"""
        if self.image is None:
            return
        if event.delta > 0:
            self.zoom = min(8.0, self.zoom * 1.15)
        else:
            self.zoom = max(0.2, self.zoom / 1.15)
        self._update_display()

    def _on_zoom_key(self, event):
        """Ctrl + +/- zoom"""
        if self.image is None:
            return
        if event.keysym in ("plus", "equal", "KP_Add"):
            self.zoom = min(8.0, self.zoom * 1.15)
        else:
            self.zoom = max(0.2, self.zoom / 1.15)
        self._update_display()

    def _on_pan_press(self, event):
        """Middle-button press: start pan"""
        self._pan_start = (event.x - self.pan_x, event.y - self.pan_y)

    def _on_pan_move(self, event):
        """Middle-button drag: pan view (throttled to avoid flicker)"""
        if self._pan_start:
            self.pan_x = event.x - self._pan_start[0]
            self.pan_y = event.y - self._pan_start[1]
            # Coalesce rapid motion events into one redraw per ~30ms.
            if self._pan_redraw_after is None:
                self._pan_redraw_after = self.after(30, self._do_pan_redraw)

    def _do_pan_redraw(self):
        self._pan_redraw_after = None
        self._update_display()

    def _on_pan_release(self, event):
        """Middle-button release: end pan"""
        self._pan_start = None
        if self._pan_redraw_after is not None:
            self.after_cancel(self._pan_redraw_after)
            self._pan_redraw_after = None
        self._update_display()

    def set_image(self, image_array: np.ndarray):
        """Set image and initialize masks"""
        if image_array is None:
            return
        self.image = image_array.copy()
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        h, w = image_array.shape[:2]
        self.accumulated_mask = np.zeros((h, w), dtype=np.uint8)
        self.preview_mask = np.zeros((h, w), dtype=np.uint8)
        self.stroke_history = []
        self._update_display()
    
    def set_mode(self, mode: str):
        """Set interaction mode: 'view', 'rect', 'ellipse', 'brush', 'curve', 'crop'"""
        self.mode = mode
        if mode != 'crop':
            self.crop_rect = None
            self.crop_finished = False
        cursors = {
            'brush': 'plus',
            'curve': 'pencil',
            'view': 'arrow',
            'crop': 'crosshair'
        }
        self.label.config(cursor=cursors.get(mode, 'crosshair'))
    
    def undo(self):
        """Undo last stroke"""
        if self.stroke_history:
            self.stroke_history.pop()
            self._rebuild_accumulated_mask()
            self._update_display()
            return True
        return False
    
    def reset_selection(self):
        """Reset all selections"""
        if self.image is not None:
            h, w = self.image.shape[:2]
            self.accumulated_mask.fill(0)
            self.preview_mask.fill(0)
            self.stroke_history = []
            self.current_path = []
            self._update_display()
    
    def get_accumulated_mask(self):
        """Get the accumulated foreground mask"""
        return self.accumulated_mask.copy() if self.accumulated_mask is not None else None
    
    def _on_frame_configure(self, event):
        """Handle frame resize events"""
        # Only update if size actually changed
        if event.width != self.last_width or event.height != self.last_height:
            self.last_width = event.width
            self.last_height = event.height
            self._update_display()
    
    def _rebuild_accumulated_mask(self):
        """Rebuild accumulated mask from history"""
        if self.image is None:
            return
        h, w = self.image.shape[:2]
        self.accumulated_mask.fill(0)
        for mask in self.stroke_history:
            self.accumulated_mask = cv2.bitwise_or(self.accumulated_mask, mask)
    
    def _on_mouse_move(self, event):
        """Mouse move event for cursor positioning"""
        if self.mode == 'view' or self.image is None:
            return
    
    def _on_mouse_press(self, event):
        """Mouse press event"""
        if self.mode == 'view' or self.image is None:
            return

        self.is_selecting = True
        img_point = self._display_to_image(event.x, event.y)

        if img_point is not None:
            self.start_point = img_point
            self.current_path = [img_point]
            self.preview_mask.fill(0)
            if self.mode == 'crop':
                self.crop_finished = False
    
    def _on_mouse_drag(self, event):
        """Mouse drag event"""
        if not self.is_selecting or self.image is None:
            return

        img_point = self._display_to_image(event.x, event.y)
        if img_point is None:
            return

        # Detect modifier keys
        ctrl = (event.state & 0x0004) != 0
        shift = (event.state & 0x0001) != 0

        # Draw preview based on mode
        if self.mode in ['brush', 'curve']:
            self.current_path.append(img_point)
            self.preview_mask.fill(0)

            # Draw line from previous point to current point
            if len(self.current_path) > 1:
                prev_pt = self.current_path[-2]
                curr_pt = self.current_path[-1]
                cv2.line(self.preview_mask, tuple(map(int, prev_pt)), tuple(map(int, curr_pt)),
                        255, self.brush_width)
        elif self.mode == 'crop':
            self.preview_mask.fill(0)
            sx, sy = int(self.start_point[0]), int(self.start_point[1])
            cx, cy = int(img_point[0]), int(img_point[1])

            if ctrl and shift:
                # Centered square
                dx = max(abs(cx - sx), abs(cy - sy))
                x1, y1 = sx - dx, sy - dx
                x2, y2 = sx + dx, sy + dy
            elif ctrl:
                # Centered rectangle
                dx, dy = abs(cx - sx), abs(cy - sy)
                x1, y1 = sx - dx, sy - dy
                x2, y2 = sx + dx, sy + dy
            elif shift:
                # Square from corner
                dx = max(abs(cx - sx), abs(cy - sy))
                x_dir = 1 if cx >= sx else -1
                y_dir = 1 if cy >= sy else -1
                x1, y1 = sx, sy
                x2, y2 = sx + dx * x_dir, sy + dx * y_dir
            else:
                # Normal rectangle
                x1, y1 = min(sx, cx), min(sy, cy)
                x2, y2 = max(sx, cx), max(sy, cy)

            # Clamp to image bounds
            h, w = self.image.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            self.crop_rect = (x1, y1, x2, y2)
            cv2.rectangle(self.preview_mask, (x1, y1), (x2, y2), 255, -1)
        elif self.mode == 'rect':
            self.preview_mask.fill(0)
            x1, y1 = int(self.start_point[0]), int(self.start_point[1])
            x2, y2 = int(img_point[0]), int(img_point[1])
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            cv2.rectangle(self.preview_mask, (x1, y1), (x2, y2), 255, -1)
        elif self.mode == 'ellipse':
            self.preview_mask.fill(0)
            center_x = int((self.start_point[0] + img_point[0]) / 2)
            center_y = int((self.start_point[1] + img_point[1]) / 2)
            ax = max(1, int(abs(img_point[0] - self.start_point[0]) / 2))
            ay = max(1, int(abs(img_point[1] - self.start_point[1]) / 2))
            cv2.ellipse(self.preview_mask, (center_x, center_y), (ax, ay), 0, 0, 360, 255, -1)

        self._update_display()
    
    def _on_mouse_release(self, event):
        """Mouse release event"""
        if not self.is_selecting or self.image is None:
            return

        self.is_selecting = False

        if self.mode == 'crop':
            if self.crop_rect is not None:
                self.crop_finished = True
                if self.on_selection_callback:
                    self.on_selection_callback({'type': 'crop', 'rect': self.crop_rect})
            self._update_display()
            return

        # Finalize the stroke
        if np.any(self.preview_mask > 0):
            # Add to history and accumulate
            self.stroke_history.append(self.preview_mask.copy())
            self.accumulated_mask = cv2.bitwise_or(self.accumulated_mask, self.preview_mask)

        self.preview_mask.fill(0)
        self.current_path = []
        self._update_display()
    
    def _display_to_image(self, display_x: int, display_y: int):
        """Convert display coordinates to image coordinates with accurate mapping"""
        if self.display_rect is None or self.image is None:
            return None
        
        x0, y0, width, height = self.display_rect
        
        # Check if click is within display area
        if display_x < x0 or display_y < y0 or display_x >= x0 + width or display_y >= y0 + height:
            return None
        
        # Convert to image coordinates
        img_x = int((display_x - x0) * self.scale_x)
        img_y = int((display_y - y0) * self.scale_y)
        
        # Clamp to image bounds
        img_x = max(0, min(img_x, self.image.shape[1] - 1))
        img_y = max(0, min(img_y, self.image.shape[0] - 1))
        
        return (img_x, img_y)
    
    def _update_display(self):
        """Update the displayed image with current selection preview"""
        if self.image is None:
            return
        
        display_img = self.image.copy()
        
        # Ensure RGB format
        if len(display_img.shape) == 2:
            display_img = cv2.cvtColor(display_img, cv2.COLOR_GRAY2RGB)
        elif display_img.shape[2] == 4:
            display_img = cv2.cvtColor(display_img, cv2.COLOR_RGBA2RGB)
        
        # Get label size for scaling calculation
        self.label.update_idletasks()
        label_width = self.label.winfo_width()
        label_height = self.label.winfo_height()
        
        if label_width < 50 or label_height < 50:
            # Label not laid out yet; defer to avoid pasting an oversized image
            # that would stretch the window.
            self.after(30, self._update_display)
            return
        
        img_h, img_w = display_img.shape[:2]

        # Calculate scaling to fit image in label while maintaining aspect ratio
        # Allow upscaling when zooming (zoom > 1)
        fit_scale = min((label_width - 10) / img_w, (label_height - 10) / img_h)
        if self.zoom <= 1.0:
            scale = min(fit_scale, 1.0) * self.zoom
        else:
            scale = fit_scale * self.zoom

        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        if abs(scale - 1.0) > 1e-6:
            interp = cv2.INTER_LINEAR if scale >= 1.0 else cv2.INTER_AREA
            display_img = cv2.resize(display_img, (new_w, new_h), interpolation=interp)
            preview_display = cv2.resize(self.preview_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            accumulated_display = cv2.resize(self.accumulated_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            self.scale_x = 1.0 / scale
            self.scale_y = 1.0 / scale
        else:
            preview_display = self.preview_mask
            accumulated_display = self.accumulated_mask
            self.scale_x = 1.0
            self.scale_y = 1.0

        # Calculate actual display position in label (with pan offset)
        display_w = display_img.shape[1]
        display_h = display_img.shape[0]
        x0 = int(max(5, (label_width - display_w) // 2) + self.pan_x)
        y0 = int(max(5, (label_height - display_h) // 2) + self.pan_y)
        self.display_rect = (x0, y0, display_w, display_h)
        
        # Overlay accumulated mask in blue
        if np.any(accumulated_display > 0):
            mask_display = np.zeros_like(display_img)
            mask_display[accumulated_display > 0] = [0, 100, 255]
            display_img = cv2.addWeighted(display_img, 0.7, mask_display, 0.3, 0)

        # Overlay preview mask in green
        if np.any(preview_display > 0):
            if self.mode == 'crop' and self.crop_rect is not None:
                # Crop mode: dim outside, keep selection bright
                self._draw_crop_overlay(display_img, preview_display)
            else:
                preview_display_rgb = np.zeros_like(display_img)
                preview_display_rgb[preview_display > 0] = [0, 255, 0]
                display_img = cv2.addWeighted(display_img, 0.8, preview_display_rgb, 0.2, 0)

        # Convert to PhotoImage and composite with a minimap (鹰眼) when zoomed in
        img_rgba = Image.fromarray(display_img).convert("RGBA")
        out = Image.new("RGBA", (label_width, label_height), (255, 255, 255, 255))
        out.paste(img_rgba, (x0, y0))

        display_w, display_h = display_img.shape[1], display_img.shape[0]
        if display_w > label_width or display_h > label_height:
            self._draw_minimap(out, display_img, label_width, label_height, display_w, display_h)

        self.photo = ImageTk.PhotoImage(out.convert("RGB"))
        self.label.config(image=self.photo)

    def _draw_minimap(self, base_img, display_img, label_width, label_height, display_w, display_h):
        """Overlay a small overview map (鹰眼); view region clear, rest greyed, black border."""
        from PIL import ImageDraw
        margin = 8
        minimap_w = 120
        ih, iw = display_img.shape[0], display_img.shape[1]
        minimap_h = max(1, int(minimap_w * ih / iw))
        clear = Image.fromarray(display_img).resize((minimap_w, minimap_h), Image.LANCZOS).convert("RGBA")

        # Visible region fraction of the displayed image
        fx = min(1.0, label_width / display_w)
        fy = min(1.0, label_height / display_h)
        cx = 0.5 - (self.pan_x / display_w)
        cy = 0.5 - (self.pan_y / display_h)
        rx = (cx - fx / 2) * minimap_w
        ry = (cy - fy / 2) * minimap_h
        rw = fx * minimap_w
        rh = fy * minimap_h
        # Clamp
        rx = max(0, min(rx, minimap_w - 2))
        ry = max(0, min(ry, minimap_h - 2))
        rw = max(2, min(rw, minimap_w - rx))
        rh = max(2, min(rh, minimap_h - ry))

        # Grey translucent mask over whole map, view region pasted back clear
        masked = Image.alpha_composite(clear, Image.new("RGBA", clear.size, (90, 90, 90, 130)))
        view_box = (int(rx), int(ry), int(rx + rw), int(ry + rh))
        masked.paste(clear.crop(view_box), (view_box[0], view_box[1]))
        draw = ImageDraw.Draw(masked)
        draw.rectangle([view_box[0], view_box[1], view_box[2] - 1, view_box[3] - 1],
                       outline=(0, 0, 0, 255), width=2)
        draw.rectangle([0, 0, minimap_w - 1, minimap_h - 1], outline=(0, 0, 0, 255))

        base_img.paste(masked, (margin, margin), masked)

    def _draw_crop_overlay(self, display_img, preview_display):
        """Draw crop overlay: dim outside, yellow border inside"""
        if self.crop_rect is None:
            return
        # Dim everything outside the crop area
        dimmed = cv2.addWeighted(display_img, 0.4, np.full_like(display_img, 32), 0.6, 0)
        # Keep selection area bright
        dimmed[preview_display > 0] = display_img[preview_display > 0]
        np.copyto(display_img, dimmed)

        # Draw yellow border on crop rect (in display coords)
        x1, y1, x2, y2 = self.crop_rect
        h, w = self.image.shape[:2]
        dh, dw = display_img.shape[:2]
        sx, sy = w / dw, h / dh
        cv2.rectangle(display_img,
                     (int(x1 / sx), int(y1 / sy)),
                     (int(x2 / sx), int(y2 / sy)),
                     (255, 255, 0), 2)


class IterativeGrabCutDisplay(tk.Frame):
    """Iterative GrabCut interactive segmentation with annotation and refinement"""
    
    # 工作阶段
    STAGE_INIT_RECT = 'init_rect'      # 绘制初始矩形
    STAGE_MARKING = 'marking'          # 显示结果并允许标注/迭代
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # 阶段和状态
        self.stage = self.STAGE_INIT_RECT
        self.init_rect = None  # (x1, y1, x2, y2)

        # 前景区域绘制模式: rect / ellipse / freehand
        self.shape_mode = 'rect'
        self.init_mask = None      # 椭圆/自由曲线生成的填充 mask (图像坐标, 0/255)
        self.current_path = []     # 自由曲线累积点 (图像坐标)
        
        # 源图像和GrabCut结果
        self.image = None
        self.gc_mask = None  # GrabCut结果：FGD/PROB_FGD -> 255，REST -> 0
        self.bgd_model = None
        self.fgd_model = None
        
        # 用户标注（累积）
        self.fgd_annotation = None  # 前景硬标注 (255 = FGD, 0 = unknown)
        self.bgd_annotation = None  # 背景硬标注 (255 = BGD, 0 = unknown)
        self.annotation_mode = None  # 'fgd' 或 'bgd'
        self.brush_width = 12
        
        # 绘制状态
        self.is_drawing = False
        self.current_stroke = []
        
        # UI - 图像显示区域
        self.label = tk.Label(self, bg="white", relief="solid", borderwidth=1, cursor="crosshair")
        self.label.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 鼠标事件
        self.label.bind("<Button-1>", self._on_mouse_press)
        self.label.bind("<B1-Motion>", self._on_mouse_drag)
        self.label.bind("<ButtonRelease-1>", self._on_mouse_release)
        
        # 坐标映射
        self.display_rect = None  # (x0, y0, width, height)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.last_width = -1
        self.last_height = -1
        
        self.photo = None
        
        # Bind Configure event to handle resize
        self.bind("<Configure>", self._on_frame_configure)

        # Don't let the pasted image resize this frame (keeps window stable).
        self.pack_propagate(False)

    def set_image(self, image_array: np.ndarray):
        """Set source image and reset"""
        if image_array is None:
            return
        self.image = image_array.copy()
        h, w = image_array.shape[:2]
        self.fgd_annotation = np.zeros((h, w), dtype=np.uint8)
        self.bgd_annotation = np.zeros((h, w), dtype=np.uint8)
        self.gc_mask = None
        self.bgd_model = None
        self.fgd_model = None
        self.init_rect = None
        self.init_mask = None
        self.current_path = []
        self.stage = self.STAGE_INIT_RECT
        self.current_stroke = []
        self._update_display()

    def set_shape_mode(self, mode: str):
        """Set foreground-region draw mode: 'rect' / 'ellipse' / 'freehand'.

        Resets any in-progress region so the new mode starts clean."""
        self.shape_mode = mode
        self.init_rect = None
        self.init_mask = None
        self.current_path = []
        self.is_drawing = False
        self._update_display()
    
    def set_stage(self, stage: str):
        """Set working stage"""
        self.stage = stage
        if stage == self.STAGE_INIT_RECT:
            self.label.config(cursor="crosshair")
        elif stage == self.STAGE_MARKING:
            self.label.config(cursor="plus")
        else:
            self.label.config(cursor="arrow")
    
    def set_annotation_mode(self, mode: str):
        """Set annotation mode: 'fgd' (red) or 'bgd' (green)"""
        self.annotation_mode = mode
    
    def init_grabcut(self, on_done):
        """Initialize and run first GrabCut from the drawn foreground region, on a
        background thread. Rect uses GC_INIT_WITH_RECT; ellipse/freehand use a
        filled mask with GC_INIT_WITH_MASK.

        on_done(success: bool) is invoked on the Tk main thread when finished.
        Heavy OpenCV work runs in a worker; display updates happen in on_done."""
        if self.image is None:
            on_done(False)
            return

        image = self.image
        h, w = image.shape[:2]

        if self.shape_mode == 'rect':
            if self.init_rect is None:
                on_done(False)
                return
            x1, y1, x2, y2 = self.init_rect
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            if x2 - x1 < 10 or y2 - y1 < 10:
                on_done(False)
                return
            rect = (x1, y1, x2 - x1, y2 - y1)

            def _work():
                mask = np.zeros((h, w), dtype=np.uint8)
                bgd_model = np.zeros((1, 65), np.float64)
                fgd_model = np.zeros((1, 65), np.float64)
                cv2.grabCut(image, mask, rect, bgd_model, fgd_model, 5,
                            cv2.GC_INIT_WITH_RECT)
                gc_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
                                   255, 0).astype(np.uint8)
                return gc_mask, bgd_model, fgd_model
        else:
            if self.init_mask is None or not np.any(self.init_mask > 0):
                on_done(False)
                return
            init_mask = self.init_mask.copy()

            def _work():
                mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
                mask[init_mask > 0] = cv2.GC_PR_FGD
                bgd_model = np.zeros((1, 65), np.float64)
                fgd_model = np.zeros((1, 65), np.float64)
                cv2.grabCut(image, mask, None, bgd_model, fgd_model, 5,
                            cv2.GC_INIT_WITH_MASK)
                gc_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
                                   255, 0).astype(np.uint8)
                return gc_mask, bgd_model, fgd_model

        def _done(result, err):
            if err is not None:
                on_done(False)
                return
            gc_mask, bgd_model, fgd_model = result
            self.gc_mask = gc_mask
            self.bgd_model = bgd_model
            self.fgd_model = fgd_model
            self.stage = self.STAGE_MARKING
            self._update_display()
            on_done(True)

        self._run_bg(_work, _done)

    def apply_grabcut_with_annotation(self, on_done):
        """Apply GrabCut using accumulated annotations, on a background thread.

        on_done(success: bool) is invoked on the Tk main thread when finished."""
        if self.image is None or self.gc_mask is None:
            on_done(False)
            return

        image = self.image
        fgd_annotation = None if self.fgd_annotation is None else self.fgd_annotation.copy()
        bgd_annotation = None if self.bgd_annotation is None else self.bgd_annotation.copy()
        prev_gc = self.gc_mask.copy()
        bgd_model = self.bgd_model if self.bgd_model is not None else np.zeros((1, 65), np.float64)
        fgd_model = self.fgd_model if self.fgd_model is not None else np.zeros((1, 65), np.float64)

        def _work():
            # 创建GrabCut初始化掩码
            mask = np.full(image.shape[:2], cv2.GC_PR_BGD, dtype=np.uint8)
            if fgd_annotation is not None:
                mask[fgd_annotation > 0] = cv2.GC_FGD
            if bgd_annotation is not None:
                mask[bgd_annotation > 0] = cv2.GC_BGD
            # 应用上一次结果作为先验
            mask[prev_gc > 0] = cv2.GC_PR_FGD
            cv2.grabCut(image, mask, None, bgd_model, fgd_model, 3,
                        cv2.GC_INIT_WITH_MASK)
            gc_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
                               255, 0).astype(np.uint8)
            return gc_mask, bgd_model, fgd_model

        def _done(result, err):
            if err is not None:
                on_done(False)
                return
            gc_mask, bgd_model, fgd_model = result
            self.gc_mask = gc_mask
            self.bgd_model = bgd_model
            self.fgd_model = fgd_model
            # 清除标注，进入结果查看阶段
            if self.fgd_annotation is not None:
                self.fgd_annotation[:] = 0
            if self.bgd_annotation is not None:
                self.bgd_annotation[:] = 0
            self.current_stroke = []
            self.stage = self.STAGE_MARKING
            self._update_display()
            on_done(True)

        self._run_bg(_work, _done)

    def _run_bg(self, work_fn, done_fn):
        """Run work_fn() in a daemon thread, then done_fn(result, err) on the
        Tk main thread. work_fn must not touch Tk widgets."""
        import threading
        def _job():
            try:
                result = work_fn()
                self.after(0, lambda: done_fn(result, None))
            except Exception as e:
                self.after(0, lambda: done_fn(None, e))
        threading.Thread(target=_job, daemon=True).start()
    
    def clear_annotations(self):
        """Clear all annotations"""
        if self.fgd_annotation is not None:
            self.fgd_annotation[:] = 0
        if self.bgd_annotation is not None:
            self.bgd_annotation[:] = 0
        self.current_stroke = []
        self._update_display()
    
    def _display_to_image(self, display_x: int, display_y: int):
        """Convert display coordinates to image coordinates"""
        if self.display_rect is None or self.image is None:
            return None
        
        x0, y0, width, height = self.display_rect
        
        if display_x < x0 or display_y < y0 or display_x >= x0 + width or display_y >= y0 + height:
            return None
        
        img_x = int((display_x - x0) * self.scale_x)
        img_y = int((display_y - y0) * self.scale_y)
        
        img_x = max(0, min(img_x, self.image.shape[1] - 1))
        img_y = max(0, min(img_y, self.image.shape[0] - 1))
        
        return (img_x, img_y)
    
    def _on_mouse_press(self, event):
        """Mouse press event"""
        if self.image is None:
            return
        
        if self.stage == self.STAGE_INIT_RECT:
            img_point = self._display_to_image(event.x, event.y)
            if img_point:
                if self.shape_mode == 'freehand':
                    self.current_path = [img_point]
                else:
                    self.init_rect = (img_point[0], img_point[1], img_point[0], img_point[1])
                self.is_drawing = True
        
        elif self.stage == self.STAGE_MARKING and self.annotation_mode:
            img_point = self._display_to_image(event.x, event.y)
            if img_point:
                self.is_drawing = True
                self.current_stroke = [img_point]
    
    def _on_mouse_drag(self, event):
        """Mouse drag event"""
        if not self.is_drawing or self.image is None:
            return
        
        img_point = self._display_to_image(event.x, event.y)
        if img_point is None:
            return
        
        if self.stage == self.STAGE_INIT_RECT:
            if self.shape_mode == 'freehand':
                self.current_path.append(img_point)
            elif self.shape_mode == 'ellipse' and (event.state & 0x0001):
                # Shift held: lock to a perfect circle (square bounding box)
                x1, y1 = self.init_rect[0], self.init_rect[1]
                side = max(abs(img_point[0] - x1), abs(img_point[1] - y1))
                x2 = x1 + side if img_point[0] >= x1 else x1 - side
                y2 = y1 + side if img_point[1] >= y1 else y1 - side
                self.init_rect = (x1, y1, x2, y2)
            else:
                self.init_rect = (self.init_rect[0], self.init_rect[1], img_point[0], img_point[1])
        
        elif self.stage == self.STAGE_MARKING and self.annotation_mode:
            self.current_stroke.append(img_point)
        
        self._update_display()
    
    def _on_mouse_release(self, event):
        """Mouse release event"""
        if not self.is_drawing or self.image is None:
            return
        
        self.is_drawing = False

        # Finalize foreground region (ellipse / freehand) into a filled mask
        if self.stage == self.STAGE_INIT_RECT:
            h, w = self.image.shape[:2]
            if self.shape_mode == 'ellipse' and self.init_rect is not None:
                x1, y1, x2, y2 = self.init_rect
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                ax, ay = abs(x2 - x1) // 2, abs(y2 - y1) // 2
                m = np.zeros((h, w), dtype=np.uint8)
                cv2.ellipse(m, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
                self.init_mask = m
            elif self.shape_mode == 'freehand' and len(self.current_path) >= 3:
                pts = np.array(self.current_path, dtype=np.int32).reshape((-1, 1, 2))
                m = np.zeros((h, w), dtype=np.uint8)
                # fillPoly implicitly connects last point back to first if unclosed
                cv2.fillPoly(m, [pts], 255)
                self.init_mask = m

        # Finalize annotations
        if self.stage == self.STAGE_MARKING and self.annotation_mode and self.current_stroke:
            target = self.fgd_annotation if self.annotation_mode == 'fgd' else self.bgd_annotation
            for i in range(len(self.current_stroke) - 1):
                pt1 = tuple(map(int, self.current_stroke[i]))
                pt2 = tuple(map(int, self.current_stroke[i + 1]))
                cv2.line(target, pt1, pt2, 255, self.brush_width)
            self.current_stroke = []
        
        self._update_display()
    
    def _on_frame_configure(self, event):
        """Handle frame resize events"""
        # Only update if size actually changed
        if event.width != self.last_width or event.height != self.last_height:
            self.last_width = event.width
            self.last_height = event.height
            self._update_display()
    
    def _update_display(self):
        """Update displayed image with overlays"""
        if self.image is None:
            return
        
        display_img = self.image.copy()
        
        # Ensure RGB format
        if len(display_img.shape) == 2:
            display_img = cv2.cvtColor(display_img, cv2.COLOR_GRAY2RGB)
        elif display_img.shape[2] == 4:
            display_img = cv2.cvtColor(display_img, cv2.COLOR_RGBA2RGB)
        
        # Get label size
        self.label.update_idletasks()
        label_width = self.label.winfo_width()
        label_height = self.label.winfo_height()

        if label_width < 50 or label_height < 50:
            # Label not laid out yet; don't paste an oversized image that would
            # stretch the window. Retry once the container has a real size.
            self.after(30, self._update_display)
            return
        
        img_h, img_w = display_img.shape[:2]
        scale = min((label_width - 10) / img_w, (label_height - 10) / img_h)
        scale = min(scale, 1.0)
        
        # Resize display image if needed
        if scale < 1.0:
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            display_img = cv2.resize(display_img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            gc_display = None
            fgd_disp = None
            bgd_disp = None
            
            if self.gc_mask is not None:
                gc_display = cv2.resize(self.gc_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            if self.fgd_annotation is not None:
                fgd_disp = cv2.resize(self.fgd_annotation, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            if self.bgd_annotation is not None:
                bgd_disp = cv2.resize(self.bgd_annotation, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            
            self.scale_x = 1.0 / scale
            self.scale_y = 1.0 / scale
        else:
            new_w, new_h = img_w, img_h
            gc_display = self.gc_mask
            fgd_disp = self.fgd_annotation
            bgd_disp = self.bgd_annotation
            self.scale_x = 1.0
            self.scale_y = 1.0
        
        # Calculate display position
        display_w = display_img.shape[1]
        display_h = display_img.shape[0]
        x0 = max(5, (label_width - display_w) // 2)
        y0 = max(5, (label_height - display_h) // 2)
        self.display_rect = (x0, y0, display_w, display_h)
        
        # Overlay GrabCut result in orange (distinct from annotation red/green)
        if self.stage != self.STAGE_INIT_RECT and gc_display is not None and np.any(gc_display > 0):
            mask_overlay = np.zeros_like(display_img)
            mask_overlay[gc_display > 0] = [255, 140, 0]  # Orange (RGB) for GC foreground
            display_img = cv2.addWeighted(display_img, 0.6, mask_overlay, 0.4, 0)

        # Overlay annotations (display image is RGB)
        # Red for FGD annotation
        if fgd_disp is not None and np.any(fgd_disp > 0):
            fgd_overlay = np.zeros_like(display_img)
            fgd_overlay[fgd_disp > 0] = [255, 0, 0]  # Bright red (RGB)
            display_img = cv2.addWeighted(display_img, 0.7, fgd_overlay, 0.3, 0)

        # Green for BGD annotation
        if bgd_disp is not None and np.any(bgd_disp > 0):
            bgd_overlay = np.zeros_like(display_img)
            bgd_overlay[bgd_disp > 0] = [0, 200, 0]  # Bright green (RGB)
            display_img = cv2.addWeighted(display_img, 0.7, bgd_overlay, 0.3, 0)

        # Live-render the in-progress annotation stroke (before mouse release)
        if (self.stage == self.STAGE_MARKING and self.annotation_mode
                and len(self.current_stroke) >= 1):
            stroke_color = (255, 0, 0) if self.annotation_mode == 'fgd' else (0, 200, 0)
            brush = max(1, int(round(self.brush_width * (scale if scale < 1.0 else 1.0))))
            pts = [(int(x * scale), int(y * scale)) if scale < 1.0 else (int(x), int(y))
                   for x, y in self.current_stroke]
            if len(pts) == 1:
                cv2.circle(display_img, pts[0], max(1, brush // 2), stroke_color, -1)
            else:
                for i in range(len(pts) - 1):
                    cv2.line(display_img, pts[i], pts[i + 1], stroke_color, brush)
        
        # Draw foreground-region preview in blue while in init stage
        if self.stage == self.STAGE_INIT_RECT:
            def _to_disp(px, py):
                return (int(px * scale), int(py * scale)) if scale < 1.0 else (int(px), int(py))

            if self.shape_mode == 'freehand':
                # Live freehand path; close it visually once enough points exist
                if len(self.current_path) >= 2:
                    pts = np.array([_to_disp(x, y) for x, y in self.current_path],
                                   dtype=np.int32).reshape((-1, 1, 2))
                    closed = len(self.current_path) >= 3
                    cv2.polylines(display_img, [pts], closed, (255, 0, 0), 2)
            elif self.shape_mode == 'ellipse':
                if self.init_rect is not None:
                    x1, y1, x2, y2 = self.init_rect
                    cx, cy = _to_disp((x1 + x2) / 2, (y1 + y2) / 2)
                    ax = int(abs(x2 - x1) / 2 * (scale if scale < 1.0 else 1))
                    ay = int(abs(y2 - y1) / 2 * (scale if scale < 1.0 else 1))
                    cv2.ellipse(display_img, (cx, cy), (ax, ay), 0, 0, 360, (255, 0, 0), 2)
            else:  # rect
                if self.init_rect is not None:
                    x1, y1 = _to_disp(self.init_rect[0], self.init_rect[1])
                    x2, y2 = _to_disp(self.init_rect[2], self.init_rect[3])
                    cv2.rectangle(display_img, (x1, y1), (x2, y2), (255, 0, 0), 3)

        # Draw rectangle for result display
        elif self.stage != self.STAGE_INIT_RECT and self.init_rect:
            x1, y1, x2, y2 = self.init_rect
            if scale < 1.0:
                x1, y1, x2, y2 = int(x1 * scale), int(y1 * scale), int(x2 * scale), int(y2 * scale)
            cv2.rectangle(display_img, (x1, y1), (x2, y2), (255, 0, 0), 2)  # Blue border
        
        # Convert to PhotoImage
        pil_img = Image.fromarray(display_img)
        self.photo = ImageTk.PhotoImage(pil_img)
        self.label.config(image=self.photo)


class ImageDisplay(tk.Frame):
    """Basic image display (non-interactive)"""
    
    def __init__(self, parent, fill_mode=False, enable_zoom=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.image = None
        self.photo = None
        self.last_width = -1
        self.last_height = -1
        self.fill_mode = fill_mode
        self.enable_zoom = enable_zoom
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._pan_start = None
        self._minimap_photo = None
        self._minimap_after = None

        if self.enable_zoom:
            self.canvas = tk.Canvas(self, bg="white", highlightthickness=1,
                                    highlightbackground="black")
            self.canvas.pack(fill="both", expand=True)
            # Keep a label reference for backward compatibility
            self.label = self.canvas
        else:
            self.label = tk.Label(self, bg="white", relief="solid", borderwidth=1)
            self.label.pack(fill="both", expand=True)

        # Bind Configure event to handle resize
        self.bind("<Configure>", self._on_frame_configure)

        # Don't let the pasted image resize this frame (keeps window stable).
        self.pack_propagate(False)

        if self.enable_zoom:
            for w in (self, self.label):
                w.bind("<Control-MouseWheel>", self._on_zoom_wheel, add="+")
                w.bind("<Control-plus>", self._on_zoom_key, add="+")
                w.bind("<Control-equal>", self._on_zoom_key, add="+")
                w.bind("<Control-KP_Add>", self._on_zoom_key, add="+")
                w.bind("<Control-minus>", self._on_zoom_key, add="+")
                w.bind("<Control-KP_Subtract>", self._on_zoom_key, add="+")
                # Middle-drag pan
                w.bind("<Button-2>", self._on_pan_press, add="+")
                w.bind("<B2-Motion>", self._on_pan_move, add="+")
                w.bind("<ButtonRelease-2>", self._on_pan_release, add="+")
            # Keyboard events need focus
            self.label.bind("<Enter>", lambda e: self.label.focus_set(), add="+")

    def _on_zoom_wheel(self, event):
        if event.delta > 0:
            self.zoom = min(8.0, self.zoom * 1.15)
        else:
            self.zoom = max(0.2, self.zoom / 1.15)
        self._update_display()

    def _on_zoom_key(self, event):
        if event.keysym in ("plus", "equal", "KP_Add"):
            self.zoom = min(8.0, self.zoom * 1.15)
        else:
            self.zoom = max(0.2, self.zoom / 1.15)
        self._update_display()

    def _on_pan_press(self, event):
        self._pan_start = (event.x - self.pan_x, event.y - self.pan_y)

    def set_image(self, image_array: np.ndarray):
        """Display image"""
        if image_array is None:
            return
        self.image = image_array.copy()
        if self.enable_zoom:
            self.zoom = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0
        self._update_display()
    
    def _on_frame_configure(self, event):
        """Handle frame resize events"""
        # Only update if size actually changed
        if event.width != self.last_width or event.height != self.last_height:
            self.last_width = event.width
            self.last_height = event.height
            self._update_display()
    
    def _update_display(self):
        """Update the displayed image - auto-fit to available space"""
        if self.image is None:
            return

        # Ensure RGB format
        if len(self.image.shape) == 2:  # Grayscale
            display_img = cv2.cvtColor(self.image, cv2.COLOR_GRAY2RGB)
        elif self.image.shape[2] == 4:  # RGBA
            display_img = cv2.cvtColor(self.image, cv2.COLOR_RGBA2RGB)
        elif self.image.shape[2] == 3:
            display_img = self.image.copy()
        else:
            return

        # Get available space in label
        self.label.update_idletasks()
        max_width = self.label.winfo_width() - 10
        max_height = self.label.winfo_height() - 10

        # Not laid out yet: defer instead of pasting an oversized image that
        # would stretch the window via geometry propagation.
        if max_width < 50 or max_height < 50:
            self.after(30, self._update_display)
            return

        h, w = display_img.shape[:2]

        # Resize to fill available space (stretch to fit, no borders)
        # In fill_mode, always resize to fill the window completely
        ratio = min(max_width / w, max_height / h) * (self.zoom if self.enable_zoom else 1.0)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        if new_w != w or new_h != h or self.fill_mode:
            # Use INTER_LINEAR in fill_mode (pattern preview) to keep 1px grid lines visible
            interp = cv2.INTER_LINEAR if self.fill_mode else cv2.INTER_NEAREST
            display_img = cv2.resize(display_img, (new_w, new_h), interpolation=interp)

        # Convert to PIL and then to PhotoImage
        pil_img = Image.fromarray(display_img)
        self.photo = ImageTk.PhotoImage(pil_img)

        if self.enable_zoom:
            self._draw_on_canvas(new_w, new_h, display_img)
        else:
            self.label.config(image=self.photo)

    def _on_pan_press(self, event):
        self._pan_start = (event.x - self.pan_x, event.y - self.pan_y)

    def _on_pan_move(self, event):
        # Pan without re-rendering the PhotoImage: just move the canvas item.
        if self._pan_start:
            new_pan_x = event.x - self._pan_start[0]
            new_pan_y = event.y - self._pan_start[1]
            dx = new_pan_x - self.pan_x
            dy = new_pan_y - self.pan_y
            self.pan_x = new_pan_x
            self.pan_y = new_pan_y
            if self.enable_zoom and hasattr(self, 'canvas'):
                self.canvas.move("main_image", dx, dy)
                self._schedule_minimap_refresh()
            else:
                self._update_display()

    def _schedule_minimap_refresh(self):
        """Throttle minimap redraw during a pan drag to avoid flicker."""
        if self._minimap_after is not None:
            return
        self._minimap_after = self.after(50, self._do_minimap_refresh)

    def _do_minimap_refresh(self):
        self._minimap_after = None
        canvas = self.canvas
        canvas.delete("minimap")
        canvas.update_idletasks()
        canvas_w = canvas.winfo_width()
        canvas_h = canvas.winfo_height()
        # Recompute displayed image size from the main canvas item bbox.
        bbox = canvas.bbox("main_image")
        if not bbox:
            return
        new_w = bbox[2] - bbox[0]
        new_h = bbox[3] - bbox[1]
        if (new_w > canvas_w or new_h > canvas_h) and self.image is not None:
            self._draw_minimap(canvas, canvas_w, canvas_h, new_w, new_h, self.image)

    def _on_pan_release(self, event):
        self._pan_start = None
        # Final full redraw to keep everything consistent.
        self._update_display()

    def _draw_on_canvas(self, new_w, new_h, display_img):
        """Draw the PhotoImage on the canvas with pan offset + minimap."""
        canvas = self.canvas
        canvas.update_idletasks()
        canvas_w = canvas.winfo_width()
        canvas_h = canvas.winfo_height()
        cx = canvas_w / 2
        cy = canvas_h / 2

        canvas.delete("main_image")
        canvas.create_image(cx + self.pan_x, cy + self.pan_y, anchor="center",
                            image=self.photo, tags="main_image")
        canvas.tag_lower("main_image")  # keep minimap above the image

        # Minimap (鹰眼)
        canvas.delete("minimap")
        if (new_w > canvas_w or new_h > canvas_h) and new_w > 0 and new_h > 0:
            self._draw_minimap(canvas, canvas_w, canvas_h, new_w, new_h, display_img)

    def _draw_minimap(self, canvas, canvas_w, canvas_h, new_w, new_h, display_img):
        """Draw a small overview map (鹰眼) with the visible region kept clear."""
        from PIL import ImageDraw
        margin = 8
        minimap_w = 120
        h, w = display_img.shape[:2]
        minimap_h = max(1, int(minimap_w * h / w))

        # Visible fraction of the displayed image
        fx = min(1.0, canvas_w / new_w)
        fy = min(1.0, canvas_h / new_h)
        rx = (0.5 - self.pan_x / new_w - fx / 2) * minimap_w
        ry = (0.5 - self.pan_y / new_h - fy / 2) * minimap_h
        rw = fx * minimap_w
        rh = fy * minimap_h
        # Clamp within minimap
        rx = max(0, min(rx, minimap_w - 2))
        ry = max(0, min(ry, minimap_h - 2))
        rw = max(2, min(rw, minimap_w - rx))
        rh = max(2, min(rh, minimap_h - ry))

        # Clear thumbnail, then grey translucent mask over the whole map,
        # with the current-view region cut back to clear, black border.
        clear = Image.fromarray(display_img).resize((minimap_w, minimap_h), Image.LANCZOS).convert("RGBA")
        masked = clear.copy()
        grey = Image.new("RGBA", masked.size, (90, 90, 90, 130))
        masked = Image.alpha_composite(masked, grey)
        # Paste the clear view region back
        view_box = (int(rx), int(ry), int(rx + rw), int(ry + rh))
        clear_region = clear.crop(view_box)
        masked.paste(clear_region, (view_box[0], view_box[1]))
        # Black border around the view region and the whole map
        draw = ImageDraw.Draw(masked)
        draw.rectangle([view_box[0], view_box[1], view_box[2] - 1, view_box[3] - 1],
                       outline=(0, 0, 0, 255), width=2)
        draw.rectangle([0, 0, minimap_w - 1, minimap_h - 1], outline=(0, 0, 0, 255))

        self._minimap_photo = ImageTk.PhotoImage(masked)
        x0 = margin
        y0 = margin
        canvas.create_image(x0, y0, anchor="nw", image=self._minimap_photo, tags="minimap")


class MainWindow(tk.Tk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.title("拼豆图纸设计器 - Perler Beads Designer")
        self.geometry("1300x800")
        # Lock a sensible minimum so loading an image can never shrink the
        # window, and prevent geometry propagation from stretching it.
        self.minsize(1000, 650)
        
        # Get colors file path (dev + frozen-safe)
        colors_file = _resource_path('src', 'assets', 'colors_221.json')
        
        # Initialize modules
        self.image_processor = ImageProcessor()
        self.color_manager = ColorManager(colors_file=colors_file)
        self.pattern_generator = PatternGenerator()
        self.segmentation = ImageSegmentation()
        self.exporter = PatternExporter()
        
        # Current state
        self.current_image = None
        self.original_loaded_image = None  # Original loaded image (before any adjustment)
        self.current_mask = None
        self.mask_applied_result = None  # Result after applying mask to image
        self.current_pattern = None
        self.current_bom = None
        self.aspect_ratio = 1.0
        # Token to invalidate in-flight background segmentation results. Each
        # segmentation run captures the current value; when it changes (new
        # image loaded or a new run started) a stale worker's result is dropped.
        self._seg_token = 0
        self.loaded_filename = 'pattern'  # Original loaded filename (without extension)
        
        # Setup UI
        self._setup_ui()
        
        # Load colors
        self._load_colors()
    
    def _setup_ui(self):
        """Setup user interface"""
        # Status bar (packed first so it stays pinned to the very bottom)
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Frame(self, relief="sunken")
        status_bar.pack(side="bottom", fill="x")
        # Busy indicator (bottom-left): playful kaomoji shown while computing
        self.busy_var = tk.StringVar(value="")
        self._busy_after_id = None
        self._busy_count = 0
        busy_label = tk.Label(status_bar, textvariable=self.busy_var,
                              anchor="w", bg="lightgray", fg="#c2185b")
        busy_label.pack(side="left", padx=(4, 2))
        tk.Label(status_bar, textvariable=self.status_var,
                 anchor="w", bg="lightgray").pack(side="left", fill="x", expand=True)

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Help button overlaid on the notebook's empty top-right tab-strip area,
        # so it shares the same row as the 图像处理/图纸生成 tab labels.
        help_btn = ttk.Button(self.notebook, text="❓ 帮助", command=self._show_help)
        help_btn.place(relx=1.0, x=-6, y=4, anchor="ne")

        # Create tabs
        self._create_preprocess_tab()
        self._create_pattern_tab()

    def _show_help(self):
        """Open the embedded help document (HELP.md) in a scrollable window."""
        try:
            from src.ui.help_viewer import show_help
            help_path = _resource_path('HELP.md')
            with open(help_path, 'r', encoding='utf-8') as f:
                md = f.read()
            show_help(self, md, title="拼豆图纸设计器 · 帮助")
        except FileNotFoundError:
            messagebox.showwarning("帮助", "帮助文档未找到 (HELP.md)")
        except Exception as e:
            messagebox.showerror("帮助", f"无法打开帮助文档: {e}")

    # ---- Busy indicator (bottom-left playful kaomoji) ----
    _KAOMOJI = ["(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "(ง •_•)ง", "♪(´▽｀)", "(=^･ω･^=)",
                "φ(゜▽゜*)♪", "(~‾▿‾)~", "ヾ(⌐■_■)ノ♪", "( ˘▽˘)っ♨"]

    def _busy_start(self):
        """Begin showing an animated kaomoji busy indicator (reference counted)."""
        self._busy_count += 1
        if self._busy_count == 1:
            self._busy_tick()

    def _busy_stop(self):
        """Stop the busy indicator when the last running job finishes."""
        self._busy_count = max(0, self._busy_count - 1)
        if self._busy_count == 0:
            if self._busy_after_id is not None:
                try:
                    self.after_cancel(self._busy_after_id)
                except Exception:
                    pass
                self._busy_after_id = None
            self.busy_var.set("")

    def _busy_tick(self):
        """Rotate through playful kaomoji while jobs are running."""
        if self._busy_count <= 0:
            return
        import random
        self.busy_var.set(random.choice(self._KAOMOJI) + " 计算中…")
        self._busy_after_id = self.after(220, self._busy_tick)

    def _create_preprocess_tab(self):
        """Create preprocessing tab with sub-tabs: 基本调整, 分割, 裁剪"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="图像处理")

        # Resizable paned layout: left controls | right display
        paned = ttk.PanedWindow(frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left panel with sub-notebook
        left_panel = ttk.Frame(paned, width=180)

        # Create sub-notebook for left panel
        self.preprocess_notebook = ttk.Notebook(left_panel)
        self.preprocess_notebook.pack(fill="both", expand=True)

        # Create two sub-tabs (裁剪已合并进"基本调整")
        self._create_preprocess_basic_tab()
        self._create_preprocess_seg_tab()

        # Right panel - interactive display with dropdown menu
        right_frame = ttk.Frame(paned)

        # Add both panes (left resizable, right expands)
        paned.add(left_panel, weight=0)
        paned.add(right_frame, weight=1)

        # Top panel with dropdown menu
        top_panel = ttk.Frame(right_frame)
        top_panel.pack(fill="x", padx=2, pady=2)

        ttk.Button(top_panel, text="加载图像",
                  command=self._load_image).pack(side="left", padx=5)

        ttk.Label(top_panel, text="显示:").pack(side="left", padx=5)
        self.seg_display_var = tk.StringVar(value="原图")
        self.seg_display_combo = ttk.Combobox(top_panel,
                                             textvariable=self.seg_display_var,
                                             values=["原图", "Mask", "Mask应用结果"],
                                             state="readonly", width=15)
        self.seg_display_combo.pack(side="left", padx=5)
        self.seg_display_combo.bind("<<ComboboxSelected>>", self._on_seg_display_changed)

        # Display area
        display_frame = ttk.Frame(right_frame)
        display_frame.pack(fill="both", expand=True, padx=2, pady=2)
        # Don't let the inner image label resize this container (prevents the
        # whole window from being stretched when an image is pasted).
        display_frame.pack_propagate(False)
        self.seg_display_label = ttk.Label(display_frame, text="原图")
        self.seg_display_label.pack()

        # Create both display widgets - initially hide IGC display
        self.seg_display = InteractiveImageDisplay(display_frame, bg="white")
        self.seg_display.pack(fill="both", expand=True)

        # Iterative GrabCut display
        self.igc_display = IterativeGrabCutDisplay(display_frame, bg="white")
        self.igc_display_visible = False

    def _create_preprocess_basic_tab(self):
        """Create basic adjustment sub-tab: brightness/contrast, blur, crop, restore"""
        frame = ttk.Frame(self.preprocess_notebook)
        self.preprocess_notebook.add(frame, text="基本调整")

        # === 亮度/对比度 (从原图像Tab移来) ===
        ttk.Label(frame, text="亮度/对比度:", font=("Arial", 9, "bold")).pack(fill="x", pady=2)
        ttk.Label(frame, text="亮度:").pack(fill="x")
        self.brightness_slider = tk.Scale(frame, from_=10, to=200, orient="horizontal")
        self.brightness_slider.set(100)
        self.brightness_slider.pack(fill="x", pady=1)

        ttk.Label(frame, text="对比度:").pack(fill="x")
        self.contrast_slider = tk.Scale(frame, from_=10, to=200, orient="horizontal")
        self.contrast_slider.set(100)
        self.contrast_slider.pack(fill="x", pady=1)

        ttk.Button(frame, text="应用调整",
                  command=self._apply_adjustments).pack(fill="x", pady=1)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=3)

        # === Gaussian Blur section ===
        ttk.Label(frame, text="高斯模糊:", font=("Arial", 9, "bold")).pack(fill="x", pady=2)

        blur_size = ttk.Frame(frame)
        blur_size.pack(fill="x", pady=1)
        ttk.Label(blur_size, text="核大小:", width=6).pack(side="left")
        self.blur_kernel = tk.Spinbox(blur_size, from_=1, to=31, increment=2, width=5)
        self.blur_kernel.delete(0, tk.END)
        self.blur_kernel.insert(0, '20')
        self.blur_kernel.pack(side="left", padx=2)

        ttk.Button(frame, text="自动建议",
                  command=self._suggest_blur_kernel).pack(fill="x", pady=1)
        ttk.Button(frame, text="应用模糊",
                  command=self._apply_gaussian_blur).pack(fill="x", pady=1)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=3)

        # === 图像裁剪 (合并自"裁剪"子tab) ===
        ttk.Label(frame, text="图像裁剪:", font=("Arial", 9, "bold")).pack(fill="x", pady=2)

        instructions = (
            "操作说明:\n"
            "• 拖拽: 矩形裁剪\n"
            "• Ctrl+拖拽: 从中心\n"
            "• Shift+拖拽: 正方形\n"
            "• Ctrl+Shift: 中心正方形"
        )
        ttk.Label(frame, text=instructions, justify="left",
                 font=("Arial", 8), foreground="gray").pack(fill="x", pady=2)

        ttk.Button(frame, text="启用裁剪",
                  command=self._enable_crop_mode).pack(fill="x", pady=1)
        ttk.Button(frame, text="应用裁剪",
                  command=self._apply_crop).pack(fill="x", pady=1)
        ttk.Button(frame, text="取消裁剪",
                  command=self._cancel_crop).pack(fill="x", pady=1)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=3)

        # === 图像变换 (旋转 / 翻转) ===
        ttk.Label(frame, text="图像变换:", font=("Arial", 9, "bold")).pack(fill="x", pady=2)

        # Rotate row 1: 90° CCW / 90° CW / 180°
        f_rot = ttk.Frame(frame)
        f_rot.pack(fill="x", pady=1)
        ttk.Button(f_rot, text="↺90°",
                   command=lambda: self._apply_transform(
                       lambda: self.image_processor.rotate_90(False), "逆时针旋转90°")
                   ).pack(side="left", padx=1, expand=True, fill="x")
        ttk.Button(f_rot, text="↻90°",
                   command=lambda: self._apply_transform(
                       lambda: self.image_processor.rotate_90(True), "顺时针旋转90°")
                   ).pack(side="left", padx=1, expand=True, fill="x")
        ttk.Button(f_rot, text="180°",
                   command=lambda: self._apply_transform(
                       self.image_processor.rotate_180, "旋转180°")
                   ).pack(side="left", padx=1, expand=True, fill="x")

        # Arbitrary angle row
        f_ang = ttk.Frame(frame)
        f_ang.pack(fill="x", pady=1)
        ttk.Label(f_ang, text="角度:", width=5).pack(side="left")
        self.rotate_angle = tk.Spinbox(f_ang, from_=-180, to=180, increment=1, width=6)
        self.rotate_angle.delete(0, tk.END)
        self.rotate_angle.insert(0, '0')
        self.rotate_angle.pack(side="left", padx=2)
        ttk.Button(f_ang, text="旋转",
                   command=self._apply_arbitrary_rotation).pack(side="left", padx=2, expand=True, fill="x")

        # Flip row: horizontal / vertical (with symmetry icons)
        self._icons = getattr(self, '_icons', [])
        icon_h = self._make_symmetry_icon(vertical_axis=True)   # 水平翻转: 关于竖直轴
        icon_v = self._make_symmetry_icon(vertical_axis=False)  # 垂直翻转: 关于水平轴
        self._icons.extend([icon_h, icon_v])
        f_flip = ttk.Frame(frame)
        f_flip.pack(fill="x", pady=1)
        ttk.Button(f_flip, text="水平对称", image=icon_h, compound="left",
                   command=lambda: self._apply_transform(
                       self.image_processor.flip_horizontal, "水平对称翻转")
                   ).pack(side="left", padx=1, expand=True, fill="x")
        ttk.Button(f_flip, text="垂直对称", image=icon_v, compound="left",
                   command=lambda: self._apply_transform(
                       self.image_processor.flip_vertical, "垂直对称翻转")
                   ).pack(side="left", padx=1, expand=True, fill="x")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=3)

        # === Restore original ===
        ttk.Button(frame, text="恢复原图",
                  command=self._restore_original_image).pack(fill="x", pady=2)

    def _create_preprocess_seg_tab(self):
        """Create segmentation sub-tab (original segmentation controls)"""
        frame = ttk.Frame(self.preprocess_notebook)
        self.preprocess_notebook.add(frame, text="分割")

        # Iterative GrabCut section
        ttk.Label(frame, text="迭代GrabCut:", font=("Arial", 9, "bold")).pack(fill="x", pady=2)

        # Shape selector for the foreground region
        f_shape = ttk.Frame(frame)
        f_shape.pack(fill="x", pady=1)
        ttk.Label(f_shape, text="形状:", width=5).pack(side="left")
        self.igc_shape_var = tk.StringVar(value="矩形")
        igc_shape_combo = ttk.Combobox(f_shape, textvariable=self.igc_shape_var,
                                       values=["矩形", "椭圆", "自由曲线"],
                                       state="readonly", width=8)
        igc_shape_combo.pack(side="left", padx=2, expand=True, fill="x")
        igc_shape_combo.bind("<<ComboboxSelected>>", self._on_igc_shape_changed)
        attach_tooltip(igc_shape_combo,
            "前景区域形状:\n"
            "矩形: 拖出矩形框\n"
            "椭圆: 拖出椭圆(按住Shift为正圆)\n"
            "自由曲线: 自由绘制封闭曲线(未闭合时自动连接起止点)")

        b_rect = ttk.Button(frame, text="1. 绘制前景区域",
                  command=self._init_iterative_grabcut)
        b_rect.pack(fill="x", pady=1)
        attach_tooltip(b_rect, "进入绘制模式:按所选形状在图像上圈出前景大致范围(实时预览)")
        b_first = ttk.Button(frame, text="2. 第一次分割",
                  command=self._first_grabcut)
        b_first.pack(fill="x", pady=1)
        attach_tooltip(b_first, "基于所绘前景区域运行首次GrabCut图割,得到初步前景")

        f_anno = ttk.Frame(frame)
        f_anno.pack(fill="x", pady=1)
        b_fgd = ttk.Button(f_anno, text="前景(红)", command=lambda: self._set_annotation_mode_igc('fgd'))
        b_fgd.pack(side="left", padx=1)
        attach_tooltip(b_fgd, "切换为前景标注:涂抹应保留为前景的区域(红色)")
        b_bgd = ttk.Button(f_anno, text="背景(绿)", command=lambda: self._set_annotation_mode_igc('bgd'))
        b_bgd.pack(side="left", padx=1)
        attach_tooltip(b_bgd, "切换为背景标注:涂抹应去除的背景区域(绿色)")

        # Brush-thickness slider + live circular size preview
        f_brush = ttk.Frame(frame)
        f_brush.pack(fill="x", pady=1)
        ttk.Label(f_brush, text="笔触:").pack(side="left", padx=(2, 0))
        self.brush_size_var = tk.IntVar(value=12)  # matches IterativeGrabCutDisplay default
        brush_scale = tk.Scale(f_brush, from_=2, to=40, orient="horizontal",
                               resolution=1, length=110, showvalue=False,
                               variable=self.brush_size_var,
                               command=self._on_brush_size_changed)
        brush_scale.pack(side="left", padx=2)
        attach_tooltip(brush_scale, "拖动调整前景/背景涂抹笔触的粗细")
        self.brush_preview = tk.Canvas(f_brush, width=44, height=44,
                                       bg="white", highlightthickness=1,
                                       highlightbackground="#cccccc")
        self.brush_preview.pack(side="left", padx=3)
        attach_tooltip(self.brush_preview, "当前笔触真实粗细(圆形)")
        self._draw_brush_preview(12)

        b_iter = ttk.Button(frame, text="3. 迭代分割",
                  command=self._iterative_grabcut)
        b_iter.pack(fill="x", pady=1)
        attach_tooltip(b_iter, "结合前景/背景标注迭代优化分割结果,可反复涂抹+迭代")
        b_clear = ttk.Button(frame, text="清除标注",
                  command=self._clear_igc_annotations)
        b_clear.pack(fill="x", pady=1)
        attach_tooltip(b_clear, "清除所有前景/背景涂抹标注")
        b_apply_igc = ttk.Button(frame, text="应用分割结果",
                  command=self._apply_iterative_grabcut)
        b_apply_igc.pack(fill="x", pady=1)
        attach_tooltip(b_apply_igc, "将当前迭代分割的Mask应用为最终前景结果")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=3)

        # Automatic segmentation
        ttk.Label(frame, text="自动分割:", font=("Arial", 9, "bold")).pack(fill="x")
        # Method selector (GrabCut / Watershed / Otsu / SLIC)
        self._seg_method_map = {
            "GrabCut(矩形初始化)": "grabcut",
            "分水岭 Watershed": "watershed",
            "Otsu 自适应阈值": "otsu",
            "SLIC 超像素": "slic",
        }
        self.seg_method_var = tk.StringVar(value="GrabCut(矩形初始化)")
        method_combo = ttk.Combobox(frame, textvariable=self.seg_method_var,
                                    state="readonly", width=18,
                                    values=list(self._seg_method_map.keys()))
        method_combo.pack(fill="x", pady=1)
        attach_tooltip(method_combo,
            "自动分割算法:\n"
            "GrabCut(矩形初始化): 以居中矩形为初值做图割,主体居中时效果好\n"
            "分水岭 Watershed: 自动种子分水岭,边缘贴合,适合轮廓清晰的主体\n"
            "Otsu 自适应阈值: 一键快速二值化,适合主体与背景明暗对比强\n"
            "SLIC 超像素: 按颜色聚成小块再聚合,适合平涂/卡通素材,边缘整齐")
        ttk.Button(frame, text="执行分割",
                  command=self._segmentate_grabcut).pack(fill="x", pady=1)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=3)

        # Morphology
        ttk.Label(frame, text="形态学操作:", font=("Arial", 9, "bold")).pack(fill="x")
        ttk.Label(frame, text="核大小:").pack(fill="x")
        self.kernel_spin = tk.Spinbox(frame, from_=3, to=21, width=10)
        self.kernel_spin.delete(0, tk.END)
        self.kernel_spin.insert(0, '5')
        self.kernel_spin.pack(fill="x", pady=1)

        # Structuring element shape (名称-示意图, 名称列定宽对齐)
        shape_label = ttk.Label(frame, text="结构元素:")
        shape_label.pack(fill="x")
        attach_tooltip(shape_label,
            "结构元素(核)的形状,决定形态学操作(开/闭/腐蚀/膨胀)沿什么方向、\n"
            "以什么轮廓作用于前景Mask。下拉选择,右侧记号是该形状的示意图。")
        _shapes = [("椭圆", "●"), ("矩形", "■"), ("十字", "┼"),
                   ("垂直线", "│"), ("水平线", "─"),
                   ("斜线", "\\"), ("斜线", "/"), ("菱形", "◆")]
        _w = max(len(n) for n, _ in _shapes)  # 最长名称的全角宽度
        _vals = [n + "　" * (_w - len(n)) + " " + s for n, s in _shapes]
        self.kernel_shape_var = tk.StringVar(value=_vals[0])
        shape_combo = ttk.Combobox(frame, textvariable=self.kernel_shape_var,
                                   state="readonly", width=12,
                                   values=_vals)
        shape_combo.pack(fill="x", pady=1)
        attach_tooltip(shape_combo,
            "结构元素形状:\n"
            "椭圆 ● 平滑各向同性(默认,原圆盘)\n"
            "矩形 ■ 四方向均匀,边角明显\n"
            "十字 ┼ 仅上下左右,保留直角\n"
            "垂直线 │ / 水平线 ─ 只沿单方向作用\n"
            "斜线 \\ / 斜线 / 沿对角方向作用\n"
            "菱形 ◆ 曼哈顿距离,介于圆与方之间")

        # Row 1: open / close
        f_morph = ttk.Frame(frame)
        f_morph.pack(fill="x", pady=1)
        b_open = ttk.Button(f_morph, text="开运算", command=self._morph_open)
        b_open.pack(side="left", padx=1)
        attach_tooltip(b_open, "先腐蚀后膨胀:去除前景Mask中的小噪点/毛刺,平滑边缘")
        b_close = ttk.Button(f_morph, text="闭运算", command=self._morph_close)
        b_close.pack(side="left", padx=1)
        attach_tooltip(b_close, "先膨胀后腐蚀:填补前景Mask中的小孔洞/缝隙,连通断裂")

        # Row 2: erode / dilate
        f_morph2 = ttk.Frame(frame)
        f_morph2.pack(fill="x", pady=1)
        b_erode = ttk.Button(f_morph2, text="腐蚀", command=self._morph_erode)
        b_erode.pack(side="left", padx=1)
        attach_tooltip(b_erode, "收缩前景:去除细小连接/毛刺,缩小Mask区域")
        b_dilate = ttk.Button(f_morph2, text="膨胀", command=self._morph_dilate)
        b_dilate.pack(side="left", padx=1)
        attach_tooltip(b_dilate, "扩张前景:连接邻近区域,填补小缝隙,扩大Mask区域")

    def _create_pattern_tab(self):
        """Create pattern generation tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="图纸生成")

        # Resizable paned layout
        paned = ttk.PanedWindow(frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left panel
        left_panel = ttk.Frame(paned, width=180)
        
        ttk.Label(left_panel, text="图纸尺寸:").pack()
        
        frame_h = ttk.Frame(left_panel)
        frame_h.pack(fill="x", pady=2)
        ttk.Label(frame_h, text="高:", width=3).pack(side="left")
        self.pattern_height = tk.Spinbox(frame_h, from_=10, to=300, width=8)
        self.pattern_height.delete(0, tk.END)
        self.pattern_height.insert(0, '52')
        self.pattern_height.bind('<FocusOut>', self._on_height_changed)
        self.pattern_height.pack(side="left", padx=2)
        
        frame_w = ttk.Frame(left_panel)
        frame_w.pack(fill="x", pady=2)
        ttk.Label(frame_w, text="宽:", width=3).pack(side="left")
        self.pattern_width = tk.Spinbox(frame_w, from_=10, to=300, width=8)
        self.pattern_width.delete(0, tk.END)
        self.pattern_width.insert(0, '52')
        self.pattern_width.bind('<FocusOut>', self._on_width_changed)
        self.pattern_width.pack(side="left", padx=2)
        
        # Aspect ratio lock
        self.aspect_lock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left_panel, text="保持比例", 
                       variable=self.aspect_lock_var).pack(fill="x", pady=2)
        
        frame_c = ttk.Frame(left_panel)
        frame_c.pack(fill="x", pady=2)
        ttk.Label(frame_c, text="颜色限制:", width=8).pack(side="left")
        self.color_limit = tk.Spinbox(frame_c, from_=0, to=221, width=6,
                                      command=self._update_color_limit_hint)
        self.color_limit.delete(0, tk.END)
        self.color_limit.insert(0, '0')
        self.color_limit.pack(side="left", padx=2)
        self.color_limit.bind("<KeyRelease>", lambda e: self._update_color_limit_hint())
        self.color_limit.bind("<FocusOut>", lambda e: self._update_color_limit_hint())
        self.color_limit_hint = tk.Label(frame_c, text="", font=("Arial", 7), fg="blue")
        self.color_limit_hint.pack(side="left", padx=2)
        self._update_color_limit_hint()
        
        # Color space metric selector
        frame_metric = ttk.Frame(left_panel)
        frame_metric.pack(fill="x")
        ttk.Label(frame_metric, text="色彩空间:").pack(side="left")
        help_lbl = tk.Label(frame_metric, text="?", fg="blue", cursor="question_arrow",
                            font=("Arial", 9, "bold"))
        help_lbl.pack(side="left", padx=3)
        attach_tooltip(help_lbl,
            "颜色匹配度量说明:\n"
            "• 加权距离: 按3:6:1加权RGB,快但较粗略\n"
            "• 欧氏距离: RGB直线距离,简单直观\n"
            "• Lab色空: 感知均匀空间,适合拼豆匹配\n"
            "• CIE76: Lab空间标准色差公式\n"
            "• CIEDE2000: 最接近人眼感知,浅色/肤色最准,稍慢(推荐)")
        self.color_metric_var = tk.StringVar(value="ciede2000")
        self.color_metric_combo = ttk.Combobox(left_panel,
                                              textvariable=self.color_metric_var,
                                              values=["加权距离", "欧氏距离", "Lab色空", "CIE76", "CIEDE2000"],
                                              state="readonly", width=15)
        self.color_metric_combo.set("CIEDE2000")
        self.color_metric_combo.pack(fill="x", pady=2)
        self.color_metric_combo.bind("<<ComboboxSelected>>", self._on_color_metric_changed)

        # Detail preservation (salience) slider
        frame_sal = ttk.Frame(left_panel)
        frame_sal.pack(fill="x", pady=2)
        ttk.Label(frame_sal, text="细节保留:", width=8).pack(side="left")
        self.salience_var = tk.DoubleVar(value=1.0)
        self.salience_scale = tk.Scale(frame_sal, from_=0.0, to=2.0, resolution=0.1,
                                       orient="horizontal", variable=self.salience_var,
                                       length=70, showvalue=False,
                                       command=lambda v: self.salience_val_label.config(text=f"{float(v):.1f}"))
        self.salience_scale.pack(side="left", padx=2)
        self.salience_val_label = tk.Label(frame_sal, text="1.0", width=4,
                                           font=("Arial", 9, "bold"), fg="blue")
        self.salience_val_label.pack(side="left", padx=2)
        attach_tooltip(self.salience_scale,
            "限制颜色时保留稀有细节色的强度。\n"
            "值越大,小面积但突出的颜色(如眼睛/嘴)越容易被保留。\n"
            "仅在设置颜色限制时生效,默认1.0。")

        # Dithering checkbox
        self.dither_var = tk.BooleanVar(value=False)
        dither_cb = ttk.Checkbutton(left_panel, text="抖动(Floyd-Steinberg)",
                       variable=self.dither_var)
        dither_cb.pack(fill="x", pady=1)
        attach_tooltip(dither_cb,
            "在Lab空间做误差扩散,感知上混合颜色、保留渐变观感。\n"
            "注意: 在规则豆格上会产生'棋盘格/洒点'伪影,\n"
            "尤其强度高时。默认关闭,需要柔边时再手动开。")

        # Dither strength slider
        frame_dith = ttk.Frame(left_panel)
        frame_dith.pack(fill="x", pady=2)
        ttk.Label(frame_dith, text="抖动强度:", width=8).pack(side="left")
        self.dither_strength_var = tk.DoubleVar(value=1.0)
        self.dither_strength_scale = tk.Scale(frame_dith, from_=0.0, to=1.0, resolution=0.05,
                                       orient="horizontal", variable=self.dither_strength_var,
                                       length=70, showvalue=False,
                                       command=lambda v: self.dither_strength_val_label.config(text=f"{float(v):.2f}"))
        self.dither_strength_scale.pack(side="left", padx=2)
        self.dither_strength_val_label = tk.Label(frame_dith, text="1.00", width=4,
                                           font=("Arial", 9, "bold"), fg="blue")
        self.dither_strength_val_label.pack(side="left", padx=2)
        attach_tooltip(self.dither_strength_scale,
            "误差扩散的强度(0-1)。\n"
            "1.0=完整Floyd-Steinberg;降低可减少网格'洒点',\n"
            "同时保留部分平滑效果。仅在开启抖动时生效。")

        # High-order ICM spatial-coherence refinement (Huang TIP2015)
        self.icm_var = tk.BooleanVar(value=False)
        icm_cb = ttk.Checkbutton(left_panel, text="高阶优化(ICM空间相干)",
                       variable=self.icm_var)
        icm_cb.pack(fill="x", pady=1)
        attach_tooltip(icm_cb,
            "对每个豆格做空间相干优化: 消除孤立噪点、合并被拆散的同色区域,\n"
            "同时保留高显著性细节(边缘/眼睛)。\n"
            "生成较慢(大图纸明显)。默认关闭。")

        # ICM strength slider
        frame_icm = ttk.Frame(left_panel)
        frame_icm.pack(fill="x", pady=2)
        ttk.Label(frame_icm, text="相干强度:", width=8).pack(side="left")
        self.icm_strength_var = tk.DoubleVar(value=0.5)
        self.icm_strength_scale = tk.Scale(frame_icm, from_=0.1, to=1.0, resolution=0.05,
                                       orient="horizontal", variable=self.icm_strength_var,
                                       length=70, showvalue=False,
                                       command=lambda v: self.icm_strength_val_label.config(text=f"{float(v):.2f}"))
        self.icm_strength_scale.pack(side="left", padx=2)
        self.icm_strength_val_label = tk.Label(frame_icm, text="0.50", width=4,
                                           font=("Arial", 9, "bold"), fg="blue")
        self.icm_strength_val_label.pack(side="left", padx=2)
        attach_tooltip(self.icm_strength_scale,
            "空间相干的强度(0.1-1.0)。\n"
            "越大越平滑、噪点越少,但可能抹掉小细节。默认0.5。\n"
            "仅在开启高阶优化时生效。")

        # Use mask processed result
        self.use_mask_result_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="使用Mask处理结果", 
                       variable=self.use_mask_result_var).pack(fill="x", pady=2)
        
        ttk.Button(left_panel, text="生成图纸",
                  command=self._generate_pattern).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)

        ttk.Label(left_panel, text="导出选项:", font=("Arial", 9, "bold")).pack()

        self.show_codes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="导出预览",
                       variable=self.show_codes_var,
                       command=self._on_show_codes_toggled).pack(fill="x", pady=1)

        # Filename
        frame_fn = ttk.Frame(left_panel)
        frame_fn.pack(fill="x", pady=2)
        ttk.Label(frame_fn, text="文件名:", width=6).pack(side="left")
        self.export_filename = tk.Entry(frame_fn, width=12)
        self.export_filename.insert(0, 'pattern')
        self.export_filename.pack(side="left", padx=2, expand=True, fill="x")

        # PNG scale
        frame_scale = ttk.Frame(left_panel)
        frame_scale.pack(fill="x", pady=2)
        ttk.Label(frame_scale, text="缩放x", width=6).pack(side="left")
        self.png_scale = tk.Spinbox(frame_scale, from_=1, to=10, width=6)
        self.png_scale.delete(0, tk.END)
        self.png_scale.insert(0, '1')
        self.png_scale.pack(side="left", padx=2)

        # PDF page size
        frame_pdf = ttk.Frame(left_panel)
        frame_pdf.pack(fill="x", pady=2)
        ttk.Label(frame_pdf, text="纸张:", width=6).pack(side="left")
        self.page_size = ttk.Combobox(frame_pdf, values=["A4", "Letter"],
                                      state="readonly", width=6)
        self.page_size.set("A4")
        self.page_size.pack(side="left", padx=2)

        # Export format checkboxes
        self.export_png_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="导出PNG",
                       variable=self.export_png_var).pack(fill="x", pady=1)

        self.export_pdf_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left_panel, text="导出PDF",
                       variable=self.export_pdf_var).pack(fill="x", pady=1)

        # One-click export button
        ttk.Button(left_panel, text="一键导出",
                  command=self._one_click_export).pack(fill="x", pady=3)

        # Output directory
        ttk.Button(left_panel, text="选择输出路径",
                  command=self._select_output_dir).pack(fill="x", pady=1)

        self.output_path_label = tk.Label(left_panel, text=self.exporter.output_dir,
                                         wraplength=110, fg="blue", font=("Arial", 8))
        self.output_path_label.pack(fill="x", pady=3)

        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)

        ttk.Label(left_panel, text="物料清单:").pack()
        self.bom_list = tk.Listbox(left_panel, height=8)
        self.bom_list.pack(fill="both", expand=True, pady=2)
        
        # Right panel
        self.pattern_display = ImageDisplay(paned, fill_mode=True, enable_zoom=True, bg="white")

        # Add panes
        paned.add(left_panel, weight=0)
        paned.add(self.pattern_display, weight=1)
    
    # ===== Event handlers =====

    def _run_async(self, work_fn, on_done):
        """Run work_fn() on a background thread, then call on_done(result) back
        on the Tk main thread. Keeps the UI responsive during long OpenCV work
        (e.g. GrabCut) so the user can keep interacting / load a new image.

        work_fn runs in the worker (OpenCV/numpy only, no Tk calls). on_done
        runs on the main thread and receives whatever work_fn returned."""
        def _job():
            try:
                result = work_fn()
                self.after(0, lambda: on_done(result, None))
            except Exception as e:
                self.after(0, lambda: on_done(None, e))
        threading.Thread(target=_job, daemon=True).start()

    def _load_image(self):
        """Load image file - supports Chinese paths"""
        filepath = filedialog.askopenfilename(
            title="选择图像",
            filetypes=[("Image files", "*.jpg *.png *.bmp"), ("All files", "*.*")]
        )
        if filepath:
            try:
                # Read with Chinese path support using cv2.imdecode
                image = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError("无法读取图像文件")
                
                # Convert BGR to RGB
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                self.image_processor.original_image = image
                self.image_processor.current_image = image.copy()
                self.current_image = image.copy()
                self.original_loaded_image = image.copy()  # Save for brightness/contrast reset
                
                # Display in preprocessing interactive display (merged image-load view)
                if hasattr(self, 'seg_display'):
                    self.seg_display.set_image(image)

                # Invalidate any in-flight background segmentation from the
                # previous image so its result can't overwrite the new state.
                self._seg_token += 1

                # Store aspect ratio and filename
                h, w = image.shape[:2]
                self.aspect_ratio = h / w if w > 0 else 1.0
                basename = os.path.basename(filepath)
                self.loaded_filename = os.path.splitext(basename)[0]
                # Auto-fill filename in export tab
                self.export_filename.delete(0, tk.END)
                self.export_filename.insert(0, f"{self.loaded_filename}_拼豆图纸")

                # Reset brightness/contrast sliders
                if hasattr(self, 'brightness_slider'):
                    self.brightness_slider.set(100)
                    self.contrast_slider.set(100)

                # Auto-fill bead dimensions based on image aspect (height=50 default)
                self._auto_fill_bead_size()

                self.status_var.set(f"已加载: {os.path.basename(filepath)} ({w}x{h})")
            except Exception as e:
                messagebox.showerror("错误", f"加载图像失败: {e}")

    def _auto_fill_bead_size(self, base_height: int = 50):
        """Auto-fill bead height/width from image aspect ratio, height=base_height."""
        if not hasattr(self, 'pattern_height') or self.image_processor.current_image is None:
            return
        h, w = self.image_processor.current_image.shape[:2]
        if h <= 0 or w <= 0:
            return
        new_h = base_height
        new_w = max(10, int(round(base_height * w / h)))
        self.pattern_height.delete(0, tk.END)
        self.pattern_height.insert(0, str(new_h))
        self.pattern_width.delete(0, tk.END)
        self.pattern_width.insert(0, str(new_w))
    
    def _reset_image(self):
        """Reset to original image"""
        try:
            if self.image_processor.original_image is None:
                raise ValueError("请先加载图像")
            
            image = self.image_processor.original_image.copy()
            self.image_processor.current_image = image.copy()
            self.current_image = image.copy()
            if hasattr(self, 'seg_display'):
                self.seg_display.set_image(image)
            self.status_var.set("已重置为原图")
        except Exception as e:
            messagebox.showwarning("警告", str(e))
    
    def _apply_adjustments(self):
        """Apply brightness and contrast - always from original image"""
        try:
            if self.original_loaded_image is None:
                raise ValueError("请先加载图像")
            
            brightness = self.brightness_slider.get() / 100.0
            contrast = self.contrast_slider.get() / 100.0
            
            # Always start from the original loaded image
            image = self.original_loaded_image.copy()
            
            # Apply brightness
            if brightness != 1.0:
                image = cv2.convertScaleAbs(image, alpha=brightness, beta=0)
            
            # Apply contrast
            if contrast != 1.0:
                image = cv2.convertScaleAbs(image, alpha=contrast, beta=0)
            
            adjusted_image = np.clip(image, 0, 255).astype(np.uint8)
            self.image_processor.current_image = adjusted_image
            self.current_image = adjusted_image
            # Also update preprocessing display
            if hasattr(self, 'seg_display'):
                self.seg_display.set_image(adjusted_image)
            self.status_var.set("已应用调整")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    # ============== Iterative GrabCut Methods ==============
    
    def _on_igc_shape_changed(self, event=None):
        """Switch the iterative-GrabCut foreground-region draw shape."""
        display_to_mode = {"矩形": "rect", "椭圆": "ellipse", "自由曲线": "freehand"}
        mode = display_to_mode.get(self.igc_shape_var.get(), "rect")
        self.igc_display.set_shape_mode(mode)
        desc = {"rect": "矩形", "ellipse": "椭圆(Shift=正圆)", "freehand": "自由曲线"}[mode]
        self.status_var.set(f"前景区域形状: {desc} - 点击\"1. 绘制前景区域\"后在图像上绘制")

    def _init_iterative_grabcut(self):
        """Initialize iterative GrabCut - draw foreground region"""
        try:
            if self.current_image is None:
                messagebox.showwarning("警告", "请先加载图像")
                return

            # Switch to IGC display
            if not self.igc_display_visible:
                self.seg_display.pack_forget()
                self.igc_display.pack(fill="both", expand=True)
                self.igc_display_visible = True

            # Apply the selected shape mode
            display_to_mode = {"矩形": "rect", "椭圆": "ellipse", "自由曲线": "freehand"}
            mode = display_to_mode.get(self.igc_shape_var.get(), "rect")

            # Set image and enable region drawing
            self.igc_display.set_image(self.current_image)
            self.igc_display.set_shape_mode(mode)
            self.igc_display.set_stage(IterativeGrabCutDisplay.STAGE_INIT_RECT)
            tips = {
                "rect": "在图像上拖拽绘制矩形框住前景（蓝色框，实时预览）",
                "ellipse": "在图像上拖拽绘制椭圆圈住前景（按住Shift为正圆，实时预览）",
                "freehand": "在图像上按住拖拽自由绘制封闭曲线圈住前景（实时预览，未闭合时自动连接起止点）",
            }
            self.status_var.set(tips[mode])
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _first_grabcut(self):
        """Execute first GrabCut from the drawn foreground region"""
        try:
            if self.igc_display.image is None:
                raise ValueError("请先绘制前景区域")

            mode = self.igc_display.shape_mode
            if mode == 'rect':
                if self.igc_display.init_rect is None:
                    raise ValueError("请在图像上绘制矩形作为初始前景区域")
            else:
                if self.igc_display.init_mask is None or not np.any(self.igc_display.init_mask > 0):
                    raise ValueError("请先在图像上绘制前景区域（椭圆或自由曲线）")

            # Execute first GrabCut (background thread; UI stays responsive)
            self.status_var.set("第一次分割中… (可随时加载新图像打断)")
            self._busy_start()

            def _on_first_done(ok):
                self._busy_stop()
                if ok:
                    self.igc_display.set_stage(IterativeGrabCutDisplay.STAGE_MARKING)
                    self.status_var.set("第一次分割完成。选择标注模式（前景红色/背景绿色）并在结果上标注")
                else:
                    messagebox.showwarning("警告", "前景区域过小，请重新绘制至少 10x10 像素的区域")

            self.igc_display.init_grabcut(_on_first_done)
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _set_annotation_mode_igc(self, mode: str):
        """Set annotation mode for iterative GrabCut"""
        try:
            if self.igc_display.image is None:
                raise ValueError("请先执行初始分割")
            
            self.igc_display.set_annotation_mode(mode)
            desc = "前景（红色）" if mode == 'fgd' else "背景（绿色）"
            self.status_var.set(f"标注模式: {desc} - 在图像上涂抹以标注{desc}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _on_brush_size_changed(self, value):
        """Slider callback: update IGC brush width and refresh the preview."""
        try:
            w = int(float(value))
        except (TypeError, ValueError):
            return
        self.igc_display.brush_width = max(1, w)
        self._draw_brush_preview(w)

    def _draw_brush_preview(self, width: int):
        """Draw a filled circle showing the real brush thickness."""
        c = self.brush_preview
        c.delete("all")
        size = 44
        cx = cy = size // 2
        # Canvas circle at 1:1 pixel scale, clamped to fit inside the box.
        r = max(1, min(int(width) // 2, (size - 6) // 2))
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="#333333", outline="")

    def _clear_igc_annotations(self):
        """Clear all annotations in iterative GrabCut"""
        try:
            self.igc_display.clear_annotations()
            self.status_var.set("标注已清除")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _iterative_grabcut(self):
        """Execute iterative GrabCut refinement"""
        try:
            if self.igc_display.image is None:
                raise ValueError("请先执行初始分割")
            
            # Check if there are annotations
            has_fgd = self.igc_display.fgd_annotation is not None and np.any(self.igc_display.fgd_annotation > 0)
            has_bgd = self.igc_display.bgd_annotation is not None and np.any(self.igc_display.bgd_annotation > 0)
            
            if not has_fgd and not has_bgd:
                messagebox.showinfo("提示", "没有标注数据。请标注前景（红色）或背景（绿色）后再执行迭代")
                return
            
            # Execute iterative GrabCut (background thread; UI stays responsive)
            self.status_var.set("迭代分割中… (可随时加载新图像打断)")
            self._busy_start()

            def _on_iter_done(ok):
                self._busy_stop()
                if ok:
                    self.status_var.set("迭代分割完成。可继续标注进行微调，或点击\"应用分割结果\"保存")
                else:
                    messagebox.showerror("错误", "GrabCut执行失败")

            self.igc_display.apply_grabcut_with_annotation(_on_iter_done)
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _apply_iterative_grabcut(self):
        """Apply iterative GrabCut result: bake mask onto the original image
        (foreground keeps color, background becomes white) and show it."""
        try:
            if self.igc_display.image is None or self.igc_display.gc_mask is None:
                raise ValueError("没有可应用的分割结果")

            # Save result to current_mask
            self.current_mask = self.igc_display.gc_mask.copy()

            # Bake the mask onto the original image -> white background
            image = self.image_processor.current_image
            if len(image.shape) == 2:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                image_rgb = image.copy()
            mask_binary = (self.current_mask > 127).astype(np.uint8) * 255
            result = np.ones_like(image_rgb) * 255
            result[mask_binary == 255] = image_rgb[mask_binary == 255]
            self.mask_applied_result = result.copy()

            # Switch back to normal display and show the baked result
            if self.igc_display_visible:
                self.igc_display.pack_forget()
                self.seg_display.pack(fill="both", expand=True)
                self.igc_display_visible = False

            self.seg_display.set_image(result)
            self.seg_display.set_mode("view")
            self.seg_display_var.set("Mask应用结果")
            self.seg_display_label.config(text="Mask应用结果")
            self.status_var.set("分割结果已应用: 前景保留彩色，背景为白色")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _on_seg_display_changed(self, event=None):
        """Handle segmentation display dropdown change"""
        selected = self.seg_display_var.get()
        self.seg_display_label.config(text=selected)
        
        if selected == "原图":
            if self.current_image is not None:
                self.seg_display.set_image(self.current_image)
        elif selected == "Mask":
            if self.current_mask is not None:
                mask_display = cv2.cvtColor(self.current_mask, cv2.COLOR_GRAY2RGB)
                self.seg_display.set_image(mask_display)
            else:
                messagebox.showwarning("警告", "请先执行分割操作")
        elif selected == "Mask应用结果":
            if self.mask_applied_result is not None:
                self.seg_display.set_image(self.mask_applied_result)
            else:
                messagebox.showwarning("警告", "请先应用分割结果")
    
    def _segmentate_grabcut(self):
        """Run the selected automatic segmentation method (background thread)."""
        try:
            image = self.image_processor.current_image
            if image is None:
                raise ValueError("请先加载图像")

            image = image.copy()
            h, w = image.shape[:2]

            method = self._seg_method_map.get(self.seg_method_var.get(), "grabcut")
            method_names = {"grabcut": "GrabCut", "watershed": "分水岭",
                            "otsu": "Otsu阈值", "slic": "SLIC超像素"}
            name = method_names[method]

            self._seg_token += 1
            token = self._seg_token
            self.status_var.set(f"{name}分割中… (可随时加载新图像打断)")
            self._busy_start()

            def _work():
                if method == "watershed":
                    return self.segmentation.watershed_auto(image)
                if method == "otsu":
                    return self.segmentation.otsu_segment(image)
                if method == "slic":
                    return self.segmentation.slic_segment(image)
                x1, y1 = int(w * 0.2), int(h * 0.2)
                x2, y2 = int(w * 0.8), int(h * 0.8)
                return self.segmentation.grabcut_rect(image, x1, y1, x2, y2)

            def _done(mask, err):
                self._busy_stop()
                if err is not None:
                    messagebox.showerror("错误", str(err))
                    return
                if token != self._seg_token:
                    return  # superseded by a newer run / image load
                self.current_mask = mask
                # Display original image
                self.seg_display.set_image(image)
                self.seg_display_var.set("原图")
                self.seg_display_label.config(text="原图")
                self.status_var.set(f"{name}分割完成")

            self._run_async(_work, _done)
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _get_morph_shape(self):
        """Map the shape combobox display text to an internal shape key."""
        text = self.kernel_shape_var.get() if hasattr(self, 'kernel_shape_var') else "椭圆 ●"
        if "矩形" in text: return "rect"
        if "十字" in text: return "cross"
        if "垂直线" in text: return "vline"
        if "水平线" in text: return "hline"
        if "菱形" in text: return "diamond"
        if "斜线" in text:
            return "diag2" if "/" in text else "diag1"  # \ = diag1, / = diag2
        return "ellipse"

    def _apply_morph_result(self, mask, op_name):
        """Shared: store mask, refresh display, set status."""
        self.current_mask = mask
        mask_display = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
        self.seg_display.set_image(mask_display)
        self.seg_display_var.set("Mask")
        self.seg_display_label.config(text="Mask")
        self.status_var.set(f"{op_name}完成")

    def _morph_open(self):
        """Morphological opening"""
        try:
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            kernel = int(self.kernel_spin.get())
            mask = self.segmentation.morph_open(self.current_mask, kernel, self._get_morph_shape())
            self._apply_morph_result(mask, "开运算")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _morph_close(self):
        """Morphological closing"""
        try:
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            kernel = int(self.kernel_spin.get())
            mask = self.segmentation.morph_close(self.current_mask, kernel, self._get_morph_shape())
            self._apply_morph_result(mask, "闭运算")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _morph_erode(self):
        """Morphological erosion"""
        try:
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            kernel = int(self.kernel_spin.get())
            mask = self.segmentation.morph_erode(self.current_mask, kernel, self._get_morph_shape())
            self._apply_morph_result(mask, "腐蚀")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _morph_dilate(self):
        """Morphological dilation"""
        try:
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            kernel = int(self.kernel_spin.get())
            mask = self.segmentation.morph_dilate(self.current_mask, kernel, self._get_morph_shape())
            self._apply_morph_result(mask, "膨胀")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _on_height_changed(self, event=None):
        """Height changed - update width to maintain aspect ratio"""
        if not self.aspect_lock_var.get():
            return
        try:
            height = int(self.pattern_height.get())
            width = int(height / self.aspect_ratio)
            if width >= 10:
                self.pattern_width.delete(0, tk.END)
                self.pattern_width.insert(0, str(width))
        except:
            pass
    
    def _on_width_changed(self, event=None):
        """Width changed - update height to maintain aspect ratio"""
        if not self.aspect_lock_var.get():
            return
        try:
            width = int(self.pattern_width.get())
            height = int(width * self.aspect_ratio)
            if height >= 10:
                self.pattern_height.delete(0, tk.END)
                self.pattern_height.insert(0, str(height))
        except:
            pass
    
    def _update_color_limit_hint(self):
        """Show '无限制' hint when color limit is 0/empty or >= palette size"""
        val = self.color_limit.get().strip()
        n_palette = len(self.color_manager.palette.colors) if getattr(self, 'color_manager', None) else 221
        try:
            n = int(val)
        except (ValueError, TypeError):
            n = 0
        if val == "" or n <= 0 or n >= n_palette:
            self.color_limit_hint.config(text="无限制", fg="blue")
        else:
            self.color_limit_hint.config(text="")

    def _on_color_metric_changed(self, event=None):
        """Color metric (color space) changed"""
        metric_display_to_internal = {
            "加权距离": "weighted",
            "欧氏距离": "euclidean",
            "Lab色空": "lab",
            "CIE76": "ciede76",
            "CIEDE2000": "ciede2000"
        }
        selected = self.color_metric_var.get()
        metric = metric_display_to_internal.get(selected, "ciede2000")
        if self.color_manager:
            self.color_manager.set_color_metric(metric)
            self.status_var.set(f"色彩空间已切换: {selected}")

    # ===== 预处理：Blur / Restore =====

    def _suggest_blur_kernel(self):
        """Auto-calculate suitable kernel size based on image dimensions"""
        if self.image_processor.current_image is None:
            messagebox.showwarning("警告", "请先加载图像")
            return
        from src.core.image_processor import ImageProcessor as IP
        kernel = IP.suggest_kernel_size(self.image_processor.current_image.shape)
        self.blur_kernel.delete(0, tk.END)
        self.blur_kernel.insert(0, str(kernel))
        self.status_var.set(f"建议核大小: {kernel}x{kernel}")

    def _apply_gaussian_blur(self):
        """Apply Gaussian blur to current image"""
        try:
            if self.image_processor.current_image is None:
                raise ValueError("请先加载图像")
            kernel = int(self.blur_kernel.get())
            if kernel < 1:
                raise ValueError("核大小必须大于0")
            if kernel % 2 == 0:
                kernel += 1
                self.blur_kernel.delete(0, tk.END)
                self.blur_kernel.insert(0, str(kernel))
            self.image_processor.apply_gaussian_blur(kernel)
            self.current_image = self.image_processor.current_image.copy()
            if hasattr(self, 'seg_display'):
                self.seg_display.set_image(self.current_image)
            self.status_var.set(f"高斯模糊已应用 (核大小: {kernel}x{kernel})")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _restore_original_image(self):
        """Restore original image, discarding all preprocessing"""
        try:
            if self.image_processor.original_image is None:
                raise ValueError("请先加载图像")
            self.image_processor.reset_to_original()
            self.current_image = self.image_processor.current_image.copy()
            self.current_mask = None
            self.mask_applied_result = None
            self.current_pattern = None
            # Reset aspect ratio
            h, w = self.current_image.shape[:2]
            self.aspect_ratio = h / w if w > 0 else 1.0
            # Reset segmentation display
            if hasattr(self, 'seg_display'):
                self.seg_display.set_image(self.current_image)
                self.seg_display.set_mode('view')
                self.seg_display.reset_selection()
            # Update all displays
            if hasattr(self, 'pattern_display'):
                self.pattern_display.image = None
                self.pattern_display.photo = None
            self.status_var.set("已恢复为原始图像，所有预处理已清除")
        except Exception as e:
            messagebox.showwarning("警告", str(e))

    # ===== 预处理：裁剪 =====

    def _enable_crop_mode(self):
        """Enable crop mode on the interactive display"""
        if self.current_image is None:
            messagebox.showwarning("警告", "请先加载图像")
            return
        self.seg_display.set_image(self.current_image)
        self.seg_display.set_mode('crop')
        self.seg_display.crop_rect = None
        self.seg_display.crop_finished = False
        self.seg_display_var.set("原图")
        self.seg_display_label.config(text="裁剪模式")
        self.status_var.set("裁剪模式: 在图像上拖拽选择裁剪区域")

    def _apply_crop(self):
        """Apply the selected crop rectangle"""
        try:
            if not hasattr(self.seg_display, 'crop_rect') or self.seg_display.crop_rect is None:
                raise ValueError("请先在图像上选择裁剪区域")
            x1, y1, x2, y2 = self.seg_display.crop_rect
            if x2 - x1 < 5 or y2 - y1 < 5:
                raise ValueError("裁剪区域过小")
            self.image_processor.crop_region(x1, y1, x2, y2)
            self.current_image = self.image_processor.current_image.copy()
            self.seg_display.set_image(self.current_image)
            self.seg_display.set_mode('view')
            self.seg_display.crop_rect = None
            h, w = self.current_image.shape[:2]
            self.aspect_ratio = h / w if w > 0 else 1.0
            self.status_var.set(f"裁剪完成: 新尺寸 {w}x{h}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _cancel_crop(self):
        """Cancel crop mode"""
        self.seg_display.set_mode('view')
        self.seg_display.crop_rect = None
        self.seg_display.crop_finished = False
        if self.current_image is not None:
            self.seg_display.set_image(self.current_image)
        self.seg_display_var.set("原图")
        self.seg_display_label.config(text="原图")
        self.status_var.set("裁剪已取消")

    def _make_symmetry_icon(self, vertical_axis: bool, size: int = 20):
        """Draw a symmetry icon: a solid triangle mirrored by a dashed triangle
        about a straight axis. vertical_axis=True → axis is a vertical line
        (used for 水平对称/left-right flip); False → horizontal axis (垂直对称).

        Returns an ImageTk.PhotoImage; caller must keep a reference."""
        from PIL import ImageDraw
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        m = 2  # margin
        solid = (30, 30, 30, 255)
        dash = (30, 30, 30, 255)
        if vertical_axis:
            ax = size // 2
            # solid triangle on the left of the axis
            d.polygon([(m, m), (ax - 3, size // 2), (m, size - m)], fill=solid)
            # dashed mirror triangle on the right (outline, dashed)
            tri = [(size - m, m), (ax + 3, size // 2), (size - m, size - m)]
            self._dashed_polygon(d, tri, dash)
            # axis line
            d.line([(ax, 0), (ax, size)], fill=(120, 120, 120, 255), width=1)
        else:
            ay = size // 2
            d.polygon([(m, m), (size // 2, ay - 3), (size - m, m)], fill=solid)
            tri = [(m, size - m), (size // 2, ay + 3), (size - m, size - m)]
            self._dashed_polygon(d, tri, dash)
            d.line([(0, ay), (size, ay)], fill=(120, 120, 120, 255), width=1)
        return ImageTk.PhotoImage(img)

    @staticmethod
    def _dashed_polygon(draw, points, fill, dash: int = 2, gap: int = 2):
        """Draw a dashed closed polygon outline by dashing each edge."""
        n = len(points)
        for i in range(n):
            p1 = points[i]
            p2 = points[(i + 1) % n]
            MainWindow._dashed_line(draw, p1, p2, fill, dash, gap)

    @staticmethod
    def _dashed_line(draw, p1, p2, fill, dash: int = 2, gap: int = 2):
        """Draw a dashed line segment from p1 to p2."""
        import math
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist == 0:
            return
        dx, dy = (x2 - x1) / dist, (y2 - y1) / dist
        pos = 0.0
        while pos < dist:
            end = min(pos + dash, dist)
            draw.line([(x1 + dx * pos, y1 + dy * pos),
                       (x1 + dx * end, y1 + dy * end)], fill=fill, width=1)
            pos = end + gap

    def _apply_transform(self, transform_fn, desc: str):
        """Apply a geometric transform (rotate/flip) to the working image and
        refresh display + derived state. Leaves the pristine originals untouched
        so 恢复原图 returns to the un-transformed loaded image."""
        try:
            if self.image_processor.current_image is None:
                raise ValueError("请先加载图像")
            transform_fn()
            self.current_image = self.image_processor.current_image.copy()
            # Geometry changed → invalidate any mask / pattern built on old dims
            self.current_mask = None
            self.mask_applied_result = None
            self.current_pattern = None
            self.seg_display.set_image(self.current_image)
            self.seg_display.set_mode('view')
            self.seg_display_var.set("原图")
            self.seg_display_label.config(text="原图")
            h, w = self.current_image.shape[:2]
            self.aspect_ratio = h / w if w > 0 else 1.0
            self._auto_fill_bead_size()
            self.status_var.set(f"{desc}完成: 新尺寸 {w}x{h}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _apply_arbitrary_rotation(self):
        """Apply the arbitrary-angle rotation from the spinbox."""
        try:
            angle = float(self.rotate_angle.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("错误", "请输入有效的旋转角度")
            return
        self._apply_transform(
            lambda: self.image_processor.rotate_arbitrary(angle),
            f"旋转{angle}°")

    # ===== 图案生成 =====

    def _generate_pattern(self):
        """Generate pattern"""
        def _generate():
            try:
                # Check if using mask result is requested but not available
                if self.use_mask_result_var.get():
                    if self.mask_applied_result is None:
                        raise ValueError("已勾选'使用Mask处理结果'，但还未执行Mask应用！\n请先在图像处理标签页的「分割」中执行Mask应用。")
                    image = self.mask_applied_result
                else:
                    image = self.image_processor.current_image
                
                if image is None:
                    raise ValueError("请先加载图像")
                
                h_val = int(self.pattern_height.get())
                w_val = int(self.pattern_width.get())
                self.aspect_ratio = h_val / w_val if w_val > 0 else 1.0
                
                color_limit = int(self.color_limit.get())
                color_limit = color_limit if color_limit > 0 else None

                salience = float(self.salience_var.get()) if hasattr(self, 'salience_var') else 1.0
                dither = bool(self.dither_var.get()) if hasattr(self, 'dither_var') else False
                dither_strength = float(self.dither_strength_var.get()) if hasattr(self, 'dither_strength_var') else 1.0
                icm_on = bool(self.icm_var.get()) if hasattr(self, 'icm_var') else False
                icm_smooth = (float(self.icm_strength_var.get())
                              if icm_on and hasattr(self, 'icm_strength_var') else 0.0)

                config = PatternConfig(
                    width_beads=w_val,
                    height_beads=h_val,
                    max_colors=color_limit,
                    salience_strength=salience,
                    dither=dither,
                    dither_strength=dither_strength,
                    icm_smooth=icm_smooth
                )

                pattern, bom = self.pattern_generator.generate_pattern(
                    image,
                    self.color_manager.get_palette(),
                    config,
                    color_manager=self.color_manager
                )

                # Derive a bead-level mask aligned with the pattern grid so the
                # chart renderer can fade masked-out cells on export/preview.
                bead_mask = None
                if self.use_mask_result_var.get() and self.current_mask is not None:
                    m = cv2.resize(self.current_mask, (w_val, h_val),
                                   interpolation=cv2.INTER_AREA)
                    bead_mask = (m > 127)

                    # 非白即前景: mask 按 >127 离散与颜色量化是两条独立管线,边缘格
                    # 可能量化成真实色却被 mask 判成背景(有颜色无编号)。逐格核对——
                    # 量化色明显非白的格子强制视为前景,保证前景格都有编号、与 mask
                    # 一一对应。背景已被烘焙为纯白,故非白判定干净。
                    pattern_arr = self.pattern_generator.get_pattern()
                    if pattern_arr is not None and \
                            pattern_arr.shape[:2] == bead_mask.shape:
                        nonwhite = np.any(pattern_arr[..., :3] < MASK_WHITE_THRESHOLD,
                                          axis=-1)
                        bead_mask = bead_mask | nonwhite
                self.pattern_generator.bead_mask = bead_mask

                # When masked, rebuild the BOM counting only foreground beads so
                # the masked-out background is excluded everywhere (sidebar BOM
                # list, exported JSON/CSV, and the chart's BOM chip bar).
                if bead_mask is not None:
                    bom = self.pattern_generator.rebuild_bom_with_mask(
                        bead_mask, self.color_manager.get_palette())

                self.current_pattern = pattern
                self.current_bom = bom

                self.pattern_display.set_image(pattern)
                self._update_bom_list(bom)

                self.status_var.set(f"图案生成成功: {w_val}x{h_val}, 使用{len(bom['colors'])}种颜色")

                # Auto-render with current checkbox state (grid or codes+grid)
                self.pattern_display.after(100, self._on_show_codes_toggled)
            except Exception as e:
                messagebox.showerror("错误", str(e))
        
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
    
    def _render_pattern_grid(self):
        """Render with grid"""
        try:
            pattern = self.pattern_generator.get_pattern()
            if pattern is None:
                raise ValueError("请先生成图案")
            
            bead_size = CHART_BEAD_SIZE
            rendered = self.pattern_generator.render_pattern_with_grid(bead_size)
            
            self.pattern_display.set_image(rendered)
            self.status_var.set("带网格渲染完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _on_show_codes_toggled(self):
        """Toggle between grid-only and codes+grid preview"""
        try:
            pattern = self.pattern_generator.get_pattern()
            if pattern is None:
                self.show_codes_var.set(False)
                return

            bead_size = CHART_BEAD_SIZE
            if self.show_codes_var.get():
                rendered = self.pattern_generator.render_standard_chart(
                    bead_size, palette=self.color_manager.get_palette(),
                    bead_mask=self.pattern_generator.bead_mask)
                self.status_var.set("标准图纸预览")
            else:
                rendered = self.pattern_generator.render_pattern_with_grid(bead_size)
                self.status_var.set("网格预览")

            self.pattern_display.set_image(rendered)
        except Exception as e:
            # If error occurs, ensure checkbox is unchecked
            self.show_codes_var.set(False)
            # Fall back to grid
            try:
                bead_size = CHART_BEAD_SIZE
                rendered = self.pattern_generator.render_pattern_with_grid(bead_size)
                self.pattern_display.set_image(rendered)
            except:
                pass
    
    def _update_bom_list(self, bom):
        """Update BOM list"""
        self.bom_list.delete(0, tk.END)
        
        for code, color_info in sorted(bom['colors'].items()):
            text = f"{code}: {color_info['name']} - {color_info['count']}粒"
            self.bom_list.insert(tk.END, text)
        
        self.bom_list.insert(tk.END, f"总计: {bom['total_beads']}粒")
    
    def _one_click_export(self):
        """一键导出: 根据复选框勾选的格式，统一导出所选文件"""
        try:
            pattern = self.pattern_generator.get_pattern()
            bom = self.pattern_generator.get_bom()

            if pattern is None:
                raise ValueError("请先生成图案")

            scale = int(self.png_scale.get())
            bead_size = CHART_BEAD_SIZE
            filename = self.export_filename.get() or f"{self.loaded_filename}_拼豆图纸"
            page_size = self.page_size.get()

            export_any = False
            export_paths = []

            # 预先渲染标准图纸(编码+粗细分网格+刻度+用量条)
            rendered_chart = self.pattern_generator.render_standard_chart(
                bead_size, palette=self.color_manager.get_palette(),
                bead_mask=self.pattern_generator.bead_mask)

            if self.export_png_var.get():
                # PNG: 导出标准图纸
                p2 = self.exporter.export_png_standard(rendered_chart,
                    f"{filename}_图纸", scale)
                export_paths.append(f"PNG标准图纸: {p2}")
                export_any = True

            if self.export_pdf_var.get():
                # PDF: 使用标准图纸图像
                filepath = self.exporter.export_pdf(
                    rendered_chart, bom, filename, page_size, title=filename)
                export_paths.append(f"PDF: {filepath}")
                export_any = True

            if not export_any:
                raise ValueError("请至少勾选一个导出格式")

            msg = "一键导出完成:\n" + "\n".join(export_paths)
            messagebox.showinfo("成功", msg)
            self.status_var.set("一键导出完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _select_output_dir(self):
        """Select output directory"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.exporter.output_dir = directory
            self.output_path_label.config(text=directory)
            self.status_var.set("输出目录已设置")
    
    def _load_colors(self):
        """Load colors from local colors.json (no remote scraping)."""
        try:
            palette = self.color_manager.get_palette()
            count = len(palette.colors) if palette is not None else 0
            self.status_var.set(f"已加载颜色表: {count} 种颜色")
        except Exception:
            self.status_var.set("颜色加载失败，使用默认颜色库")


if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
