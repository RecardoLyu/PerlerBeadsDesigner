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
from src.core.pattern_generator import PatternGenerator, PatternConfig
from src.utils.segmentation import ImageSegmentation
from src.utils.export import PatternExporter
# Note: remote web scraper disabled to prefer local colors.json


class InteractiveImageDisplay(tk.Frame):
    """Interactive image display with accumulated foreground selection and undo support"""
    
    def __init__(self, parent, mode='view', on_selection_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.image = None
        self.photo = None
        self.mode = mode  # 'view', 'rect', 'ellipse', 'brush', 'curve'
        self.on_selection_callback = on_selection_callback
        
        # Foreground accumulation
        self.accumulated_mask = None  # Accumulated foreground from all strokes
        self.stroke_history = []  # Stack of masks for undo
        
        # Current selection state
        self.is_selecting = False
        self.start_point = None
        self.current_path = []  # For curve/brush strokes
        self.preview_mask = None  # For preview during drawing
        
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
        
        # Bind mouse events
        self.label.bind("<Button-1>", self._on_mouse_press)
        self.label.bind("<B1-Motion>", self._on_mouse_drag)
        self.label.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.label.bind("<Motion>", self._on_mouse_move)
        
        # Bind Configure event to handle resize
        self.bind("<Configure>", self._on_frame_configure)
    
    def set_image(self, image_array: np.ndarray):
        """Set image and initialize masks"""
        if image_array is None:
            return
        self.image = image_array.copy()
        h, w = image_array.shape[:2]
        self.accumulated_mask = np.zeros((h, w), dtype=np.uint8)
        self.preview_mask = np.zeros((h, w), dtype=np.uint8)
        self.stroke_history = []
        self._update_display()
    
    def set_mode(self, mode: str):
        """Set interaction mode: 'view', 'rect', 'ellipse', 'brush', 'curve'"""
        self.mode = mode
        cursors = {
            'brush': 'plus',
            'curve': 'pencil',
            'view': 'arrow'
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
    
    def _on_mouse_drag(self, event):
        """Mouse drag event"""
        if not self.is_selecting or self.image is None:
            return
        
        img_point = self._display_to_image(event.x, event.y)
        if img_point is None:
            return
        
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
            label_width, label_height = 800, 600
        
        img_h, img_w = display_img.shape[:2]
        
        # Calculate scaling to fit image in label while maintaining aspect ratio
        scale = min((label_width - 10) / img_w, (label_height - 10) / img_h)
        scale = min(scale, 1.0)  # Don't upscale
        
        if scale < 1.0:
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            display_img = cv2.resize(display_img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Scale masks too
            preview_display = cv2.resize(self.preview_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            accumulated_display = cv2.resize(self.accumulated_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            
            self.scale_x = 1.0 / scale
            self.scale_y = 1.0 / scale
        else:
            preview_display = self.preview_mask
            accumulated_display = self.accumulated_mask
            self.scale_x = 1.0
            self.scale_y = 1.0
        
        # Calculate actual display position in label
        display_w = display_img.shape[1]
        display_h = display_img.shape[0]
        x0 = max(5, (label_width - display_w) // 2)
        y0 = max(5, (label_height - display_h) // 2)
        self.display_rect = (x0, y0, display_w, display_h)
        
        # Overlay accumulated mask in blue
        if np.any(accumulated_display > 0):
            mask_display = np.zeros_like(display_img)
            mask_display[accumulated_display > 0] = [0, 100, 255]
            display_img = cv2.addWeighted(display_img, 0.7, mask_display, 0.3, 0)
        
        # Overlay preview mask in green
        if np.any(preview_display > 0):
            preview_display_rgb = np.zeros_like(display_img)
            preview_display_rgb[preview_display > 0] = [0, 255, 0]
            display_img = cv2.addWeighted(display_img, 0.8, preview_display_rgb, 0.2, 0)
        
        # Convert to PhotoImage
        pil_img = Image.fromarray(display_img)
        self.photo = ImageTk.PhotoImage(pil_img)
        self.label.config(image=self.photo)


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
        self.stage = self.STAGE_INIT_RECT
        self.current_stroke = []
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
    
    def init_grabcut_with_rect(self):
        """Initialize and run first GrabCut with rectangle"""
        if self.image is None or self.init_rect is None:
            return False
        
        x1, y1, x2, y2 = self.init_rect
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # 确保矩形有效
        if x2 - x1 < 10 or y2 - y1 < 10:
            return False
        
        # 执行初始GrabCut
        mask = np.zeros(self.image.shape[:2], dtype=np.uint8)
        self.bgd_model = np.zeros((1, 65), np.float64)
        self.fgd_model = np.zeros((1, 65), np.float64)
        
        cv2.grabCut(
            self.image,
            mask,
            (x1, y1, x2 - x1, y2 - y1),
            self.bgd_model,
            self.fgd_model,
            5,
            cv2.GC_INIT_WITH_RECT
        )
        
        self.gc_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        self.stage = self.STAGE_MARKING
        self._update_display()
        return True
    
    def apply_grabcut_with_annotation(self):
        """Apply GrabCut using accumulated annotations"""
        if self.image is None or self.gc_mask is None:
            return False
        
        # 创建GrabCut初始化掩码
        mask = np.zeros(self.image.shape[:2], dtype=np.uint8)
        mask[:, :] = cv2.GC_PR_BGD  # 默认可能背景
        
        # 应用前景标注
        if self.fgd_annotation is not None:
            mask[self.fgd_annotation > 0] = cv2.GC_FGD
        
        # 应用背景标注
        if self.bgd_annotation is not None:
            mask[self.bgd_annotation > 0] = cv2.GC_BGD
        
        # 应用上一次结果作为先验
        mask[self.gc_mask > 0] = cv2.GC_PR_FGD
        
        # 执行迭代GrabCut
        if self.bgd_model is None:
            self.bgd_model = np.zeros((1, 65), np.float64)
        if self.fgd_model is None:
            self.fgd_model = np.zeros((1, 65), np.float64)
        
        cv2.grabCut(
            self.image,
            mask,
            None,
            self.bgd_model,
            self.fgd_model,
            3,
            cv2.GC_INIT_WITH_MASK
        )
        
        self.gc_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        
        # 清除标注，进入结果查看阶段
        self.fgd_annotation[:] = 0
        self.bgd_annotation[:] = 0
        self.current_stroke = []
        self.stage = self.STAGE_MARKING
        self._update_display()
        return True
    
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
            self.init_rect = (self.init_rect[0], self.init_rect[1], img_point[0], img_point[1])
        
        elif self.stage == self.STAGE_MARKING and self.annotation_mode:
            self.current_stroke.append(img_point)
        
        self._update_display()
    
    def _on_mouse_release(self, event):
        """Mouse release event"""
        if not self.is_drawing or self.image is None:
            return
        
        self.is_drawing = False
        
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
            label_width, label_height = 800, 600
        
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
        
        # Overlay GrabCut result in blue
        if self.stage != self.STAGE_INIT_RECT and gc_display is not None and np.any(gc_display > 0):
            mask_overlay = np.zeros_like(display_img)
            mask_overlay[gc_display > 0] = [255, 0, 0]  # Red for FGD
            display_img = cv2.addWeighted(display_img, 0.6, mask_overlay, 0.4, 0)
        
        # Overlay annotations
        # Red for FGD annotation
        if fgd_disp is not None and np.any(fgd_disp > 0):
            fgd_overlay = np.zeros_like(display_img)
            fgd_overlay[fgd_disp > 0] = [0, 0, 255]  # Bright red
            display_img = cv2.addWeighted(display_img, 0.7, fgd_overlay, 0.3, 0)
        
        # Green for BGD annotation
        if bgd_disp is not None and np.any(bgd_disp > 0):
            bgd_overlay = np.zeros_like(display_img)
            bgd_overlay[bgd_disp > 0] = [0, 255, 0]  # Bright green
            display_img = cv2.addWeighted(display_img, 0.7, bgd_overlay, 0.3, 0)
        
        # Draw rectangle in blue if in init stage
        if self.stage == self.STAGE_INIT_RECT and self.init_rect:
            x1, y1, x2, y2 = self.init_rect
            if scale < 1.0:
                x1, y1, x2, y2 = int(x1 * scale), int(y1 * scale), int(x2 * scale), int(y2 * scale)
            cv2.rectangle(display_img, (x1, y1), (x2, y2), (255, 0, 0), 3)  # Blue
        
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
    
    def __init__(self, parent, fill_mode=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.image = None
        self.photo = None
        self.last_width = -1
        self.last_height = -1
        self.fill_mode = fill_mode
        
        self.label = tk.Label(self, bg="white", relief="solid", borderwidth=1)
        self.label.pack(fill="both", expand=True)
        
        # Bind Configure event to handle resize
        self.bind("<Configure>", self._on_frame_configure)
    
    def set_image(self, image_array: np.ndarray):
        """Display image"""
        if image_array is None:
            return
        self.image = image_array.copy()
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

        # Fallback to default if not yet rendered
        if max_width < 50:
            max_width = 800
        if max_height < 50:
            max_height = 600

        h, w = display_img.shape[:2]

        # Resize to fill available space (stretch to fit, no borders)
        # In fill_mode, always resize to fill the window completely
        ratio = min(max_width / w, max_height / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        if new_w != w or new_h != h or self.fill_mode:
            display_img = cv2.resize(display_img, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

        # Convert to PIL and then to PhotoImage
        pil_img = Image.fromarray(display_img)
        self.photo = ImageTk.PhotoImage(pil_img)
        self.label.config(image=self.photo)


class MainWindow(tk.Tk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.title("拼豆图纸设计器 - Perler Beads Designer")
        self.geometry("1300x800")
        
        # Get colors file path
        colors_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  'assets', 'colors_221.json')
        
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
        self.loaded_filename = 'pattern'  # Original loaded filename (without extension)
        
        # Setup UI
        self._setup_ui()
        
        # Load colors
        self._load_colors()
    
    def _setup_ui(self):
        """Setup user interface"""
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create tabs
        self._create_image_tab()
        self._create_segmentation_tab()
        self._create_pattern_tab()
        self._create_export_tab()
        
        # Status bar
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(self, textvariable=self.status_var, relief="sunken", 
                             anchor="w", bg="lightgray")
        status_bar.pack(side="bottom", fill="x")
    
    def _create_image_tab(self):
        """Create image loading and processing tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="图像加载")
        
        # Left panel - narrow control panel
        left_panel = ttk.Frame(frame, width=120)
        left_panel.pack(side="left", fill="y", padx=2, pady=5)
        left_panel.pack_propagate(False)
        
        ttk.Button(left_panel, text="加载图像", 
                  command=self._load_image).pack(fill="x", pady=1)
        ttk.Button(left_panel, text="重置为原图", 
                  command=self._reset_image).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        # Brightness/Contrast
        ttk.Label(left_panel, text="亮度:").pack()
        self.brightness_slider = tk.Scale(left_panel, from_=10, to=200, orient="horizontal")
        self.brightness_slider.set(100)
        self.brightness_slider.pack(fill="x", pady=2)
        
        ttk.Label(left_panel, text="对比度:").pack()
        self.contrast_slider = tk.Scale(left_panel, from_=10, to=200, orient="horizontal")
        self.contrast_slider.set(100)
        self.contrast_slider.pack(fill="x", pady=2)
        
        ttk.Button(left_panel, text="应用调整", 
                  command=self._apply_adjustments).pack(fill="x", pady=1)
        
        # Right panel - image display
        self.image_display = ImageDisplay(frame, bg="white")
        self.image_display.pack(side="right", fill="both", expand=True, padx=2, pady=5)
    
    def _create_segmentation_tab(self):
        """Create segmentation tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="前景分割")
        
        # Left panel
        left_panel = ttk.Frame(frame, width=130)
        left_panel.pack(side="left", fill="y", padx=2, pady=5)
        left_panel.pack_propagate(False)
        
        # Interactive selection section
        ttk.Label(left_panel, text="交互式选择:", font=("Arial", 10, "bold")).pack(fill="x", pady=5)
        
        ttk.Label(left_panel, text="选择模式:").pack(fill="x")
        self.interactive_mode_var = tk.StringVar(value="矩形")
        self.interactive_mode_combo = ttk.Combobox(left_panel,
                                                   textvariable=self.interactive_mode_var,
                                                   values=["矩形", "椭圆", "涂抹"],
                                                   state="readonly", width=15)
        self.interactive_mode_combo.pack(fill="x", pady=2)
        self.interactive_mode_combo.bind("<<ComboboxSelected>>", self._on_interactive_mode_changed)
        
        frame_interactive = ttk.Frame(left_panel)
        frame_interactive.pack(fill="x", pady=2)
        ttk.Button(frame_interactive, text="启用", command=self._enable_interactive_selection).pack(side="left", padx=1)
        ttk.Button(frame_interactive, text="撤销", command=self._undo_last_mark).pack(side="left", padx=1)
        ttk.Button(frame_interactive, text="重置", command=self._reset_interactive_selection).pack(side="left", padx=1)
        
        ttk.Button(left_panel, text="执行分割", command=self._segmentate_interactive).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        # Iterative GrabCut section
        ttk.Label(left_panel, text="迭代GrabCut分割:", font=("Arial", 10, "bold")).pack(fill="x", pady=5)
        
        ttk.Button(left_panel, text="1. 绘制初始矩形", 
                  command=self._init_iterative_grabcut).pack(fill="x", pady=1)
        
        ttk.Button(left_panel, text="2. 执行第一次分割", 
                  command=self._first_grabcut).pack(fill="x", pady=1)
        
        frame_anno = ttk.Frame(left_panel)
        frame_anno.pack(fill="x", pady=2)
        ttk.Button(frame_anno, text="前景(红)", command=lambda: self._set_annotation_mode_igc('fgd')).pack(side="left", padx=1)
        ttk.Button(frame_anno, text="背景(绿)", command=lambda: self._set_annotation_mode_igc('bgd')).pack(side="left", padx=1)
        
        ttk.Button(left_panel, text="3. 迭代分割", 
                  command=self._iterative_grabcut).pack(fill="x", pady=1)
        
        ttk.Button(left_panel, text="清除标注", 
                  command=self._clear_igc_annotations).pack(fill="x", pady=1)
        
        ttk.Button(left_panel, text="应用分割结果", 
                  command=self._apply_iterative_grabcut).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        ttk.Label(left_panel, text="分割方法:").pack()
        self.seg_method = ttk.Combobox(left_panel, 
                                       values=["GrabCut", "自适应阈值", "简单阈值"], 
                                       state="readonly", width=15)
        self.seg_method.set("GrabCut")
        self.seg_method.pack(fill="x", pady=2)
        
        ttk.Button(left_panel, text="执行分割", 
                  command=self._segmentate_grabcut).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        ttk.Label(left_panel, text="阈值:").pack()
        self.threshold_spin = tk.Spinbox(left_panel, from_=0, to=255, width=10)
        self.threshold_spin.delete(0, tk.END)
        self.threshold_spin.insert(0, '127')
        self.threshold_spin.pack(fill="x", pady=2)
        
        ttk.Button(left_panel, text="应用阈值", 
                  command=self._apply_threshold).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        ttk.Label(left_panel, text="形态学操作:").pack()
        ttk.Label(left_panel, text="核大小:").pack()
        self.kernel_spin = tk.Spinbox(left_panel, from_=3, to=21, width=10)
        self.kernel_spin.delete(0, tk.END)
        self.kernel_spin.insert(0, '5')
        self.kernel_spin.pack(fill="x", pady=2)
        
        frame_morph = ttk.Frame(left_panel)
        frame_morph.pack(fill="x", pady=2)
        ttk.Button(frame_morph, text="开运算", command=self._morph_open).pack(side="left", padx=1)
        ttk.Button(frame_morph, text="闭运算", command=self._morph_close).pack(side="left", padx=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        ttk.Button(left_panel, text="应用Mask", 
                  command=self._apply_mask_to_image).pack(fill="x", pady=1)
        
        # Right panel - interactive display with dropdown menu
        right_frame = ttk.Frame(frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=2, pady=5)
        
        # Top panel with dropdown menu
        top_panel = ttk.Frame(right_frame)
        top_panel.pack(fill="x", padx=2, pady=2)
        
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
        self.seg_display_label = ttk.Label(display_frame, text="原图")
        self.seg_display_label.pack()
        
        # Create both display widgets - initially hide IGC display
        # Interactive display (for cumulative marking mode)
        self.seg_display = InteractiveImageDisplay(display_frame, bg="white",
                                                  on_selection_callback=self._on_interactive_selection)
        self.seg_display.pack(fill="both", expand=True)
        
        # Iterative GrabCut display
        self.igc_display = IterativeGrabCutDisplay(display_frame, bg="white")
        # Initially hidden
        self.igc_display_visible = False
    
    def _create_pattern_tab(self):
        """Create pattern generation tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="图案生成")
        
        # Left panel
        left_panel = ttk.Frame(frame, width=120)
        left_panel.pack(side="left", fill="y", padx=2, pady=5)
        left_panel.pack_propagate(False)
        
        ttk.Label(left_panel, text="拼豆数量:").pack()
        ttk.Label(left_panel, text="(高, 宽)", font=("Arial", 8)).pack()
        
        frame_h = ttk.Frame(left_panel)
        frame_h.pack(fill="x", pady=2)
        ttk.Label(frame_h, text="高:", width=3).pack(side="left")
        self.pattern_height = tk.Spinbox(frame_h, from_=10, to=300, width=8)
        self.pattern_height.delete(0, tk.END)
        self.pattern_height.insert(0, '100')
        self.pattern_height.bind('<FocusOut>', self._on_height_changed)
        self.pattern_height.pack(side="left", padx=2)
        
        frame_w = ttk.Frame(left_panel)
        frame_w.pack(fill="x", pady=2)
        ttk.Label(frame_w, text="宽:", width=3).pack(side="left")
        self.pattern_width = tk.Spinbox(frame_w, from_=10, to=300, width=8)
        self.pattern_width.delete(0, tk.END)
        self.pattern_width.insert(0, '50')
        self.pattern_width.bind('<FocusOut>', self._on_width_changed)
        self.pattern_width.pack(side="left", padx=2)
        
        # Aspect ratio lock
        self.aspect_lock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left_panel, text="保持比例", 
                       variable=self.aspect_lock_var).pack(fill="x", pady=2)
        
        frame_c = ttk.Frame(left_panel)
        frame_c.pack(fill="x", pady=2)
        ttk.Label(frame_c, text="颜色限制:", width=8).pack(side="left")
        self.color_limit = tk.Spinbox(frame_c, from_=0, to=100, width=6)
        self.color_limit.delete(0, tk.END)
        self.color_limit.insert(0, '0')
        self.color_limit.pack(side="left", padx=2)
        tk.Label(frame_c, text="(0=无限)", font=("Arial", 7), fg="gray").pack(side="left", padx=2)
        
        # Color space metric selector
        ttk.Label(left_panel, text="色彩空间:").pack()
        self.color_metric_var = tk.StringVar(value="weighted")
        self.color_metric_combo = ttk.Combobox(left_panel, 
                                              textvariable=self.color_metric_var,
                                              values=["加权距离", "欧氏距离", "Lab色空", "CIE76"],
                                              state="readonly", width=15)
        self.color_metric_combo.pack(fill="x", pady=2)
        self.color_metric_combo.bind("<<ComboboxSelected>>", self._on_color_metric_changed)
        
        # Use mask processed result
        self.use_mask_result_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="使用Mask处理结果", 
                       variable=self.use_mask_result_var).pack(fill="x", pady=2)
        
        ttk.Button(left_panel, text="生成图案", 
                  command=self._generate_pattern).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        ttk.Label(left_panel, text="渲染选项:").pack()
        frame_size = ttk.Frame(left_panel)
        frame_size.pack(fill="x", pady=2)
        ttk.Label(frame_size, text="像素大小:", width=8).pack(side="left")
        self.bead_size = tk.Spinbox(frame_size, from_=5, to=100, width=6)
        self.bead_size.delete(0, tk.END)
        self.bead_size.insert(0, '20')
        self.bead_size.pack(side="left", padx=2)
        
        ttk.Button(left_panel, text="带编码渲染",
                  command=self._render_pattern_codes).pack(fill="x", pady=1)
        
        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)
        
        ttk.Label(left_panel, text="物料清单:").pack()
        self.bom_list = tk.Listbox(left_panel, height=8)
        self.bom_list.pack(fill="both", expand=True, pady=2)
        
        # Right panel
        self.pattern_display = ImageDisplay(frame, fill_mode=True, bg="white")
        self.pattern_display.pack(side="right", fill="both", expand=True, padx=2, pady=5)
    
    def _create_export_tab(self):
        """Create export tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="导出")

        left_panel = ttk.Frame(frame, width=120)
        left_panel.pack(side="left", fill="y", padx=2, pady=5)
        left_panel.pack_propagate(False)

        ttk.Label(left_panel, text="文件名:").pack()
        self.export_filename = tk.Entry(left_panel)
        self.export_filename.insert(0, 'pattern')
        self.export_filename.pack(fill="x", pady=2)

        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)

        ttk.Label(left_panel, text="导出参数:").pack()

        # Scale parameter
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
        ttk.Label(frame_pdf, text="纸张:", width=4).pack(side="left")
        self.page_size = ttk.Combobox(frame_pdf, values=["A4", "Letter"],
                                      state="readonly", width=6)
        self.page_size.set("A4")
        self.page_size.pack(side="left", padx=2)

        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)

        # Export format checkboxes - all as one unified section
        ttk.Label(left_panel, text="导出格式:", font=("Arial", 10, "bold")).pack(fill="x", pady=3)

        self.export_png_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="导出PNG",
                       variable=self.export_png_var).pack(fill="x", pady=1)

        self.export_pdf_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left_panel, text="导出PDF",
                       variable=self.export_pdf_var).pack(fill="x", pady=1)

        self.export_bom_json_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="导出物料清单(JSON)",
                       variable=self.export_bom_json_var).pack(fill="x", pady=1)

        self.export_bom_csv_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_panel, text="导出物料清单(CSV)",
                       variable=self.export_bom_csv_var).pack(fill="x", pady=1)

        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)

        # One-click export button
        ttk.Button(left_panel, text="一键导出",
                  command=self._one_click_export).pack(fill="x", pady=3)

        ttk.Separator(left_panel, orient="horizontal").pack(fill="x", pady=5)

        # Output directory
        ttk.Button(left_panel, text="选择输出路径",
                  command=self._select_output_dir).pack(fill="x", pady=1)

        self.output_path_label = tk.Label(left_panel, text=self.exporter.output_dir,
                                         wraplength=110, fg="blue", font=("Arial", 8))
        self.output_path_label.pack(fill="x", pady=3)
    
    # ===== Event handlers =====
    
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
                
                # Display original
                self.image_display.set_image(image)
                
                # Store aspect ratio and filename
                h, w = image.shape[:2]
                self.aspect_ratio = h / w if w > 0 else 1.0
                basename = os.path.basename(filepath)
                self.loaded_filename = os.path.splitext(basename)[0]
                # Auto-fill filename in export tab
                self.export_filename.delete(0, tk.END)
                self.export_filename.insert(0, f"{self.loaded_filename}_拼豆图纸")
                
                # Reset brightness/contrast sliders
                self.brightness_slider.set(100)
                self.contrast_slider.set(100)
                
                self.status_var.set(f"已加载: {os.path.basename(filepath)} ({w}x{h})")
            except Exception as e:
                messagebox.showerror("错误", f"加载图像失败: {e}")
    
    def _reset_image(self):
        """Reset to original image"""
        try:
            if self.image_processor.original_image is None:
                raise ValueError("请先加载图像")
            
            image = self.image_processor.original_image.copy()
            self.image_processor.current_image = image.copy()
            self.current_image = image.copy()
            self.image_display.set_image(image)
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
            self.image_display.set_image(adjusted_image)
            self.status_var.set("已应用调整")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _on_interactive_mode_changed(self, event=None):
        """Handle interactive mode change"""
        mode_display_to_internal = {
            "矩形": "rect",
            "椭圆": "ellipse",
            "涂抹": "brush"
        }
        selected = self.interactive_mode_var.get()
        mode = mode_display_to_internal.get(selected, "rect")
        self.seg_display.set_mode(mode)
        self.status_var.set(f"交互模式已切换: {selected}")
    
    def _enable_interactive_selection(self):
        """Enable interactive selection for segmentation"""
        if self.current_image is None:
            messagebox.showwarning("警告", "请先加载图像")
            return
        
        mode_display_to_internal = {
            "矩形": "rect",
            "椭圆": "ellipse",
            "涂抹": "brush"
        }
        selected = self.interactive_mode_var.get()
        mode = mode_display_to_internal.get(selected, "rect")
        
        self.seg_display.set_mode(mode)
        self.seg_display.set_image(self.current_image)
        self.seg_display_var.set("原图")
        self.seg_display_label.config(text="原图 (交互模式)")
        
        if mode == "涂抹":
            self.status_var.set("涂抹模式启用: 在图像上涂抹标记前景，完成后点击\"执行分割\"")
        else:
            self.status_var.set(f"{selected}模式启用: 拖动鼠标选择前景区域，释放后点击\"执行分割\"")
    
    def _reset_interactive_selection(self):
        """Reset interactive selection"""
        self.seg_display.reset_selection()
        self.status_var.set("交互选择已重置")
    
    def _on_interactive_selection(self, selection_data: dict):
        """Callback for interactive selection"""
        # For now, just store the selection data
        # Actual segmentation happens when user clicks "执行分割"
        pass
    
    def _undo_last_mark(self):
        """Undo the last interactive mark"""
        if self.seg_display.undo():
            mark_count = len(self.seg_display.stroke_history)
            self.status_var.set(f"撤销上一笔 (当前标记数: {mark_count})")
        else:
            self.status_var.set("没有可撤销的标记")
    
    def _segmentate_interactive(self):
        """Segment based on accumulated interactive selection (union of all marks)"""
        try:
            if self.current_image is None:
                raise ValueError("请先加载图像")
            
            # Get accumulated mask (union of all marks)
            accumulated_mask = self.seg_display.get_accumulated_mask()
            mark_count = len(self.seg_display.stroke_history)
            
            if accumulated_mask is None or not np.any(accumulated_mask > 0):
                raise ValueError("请先在图像上进行标记 (矩形、椭圆或涂抹)")
            
            image = self.image_processor.current_image
            
            # Create GC_FGD/GC_BGD initialization from accumulated mask
            gc_mask = np.zeros(image.shape[:2], dtype=np.uint8)
            gc_mask[accumulated_mask > 0] = cv2.GC_FGD
            
            # Run GrabCut
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)
            cv2.grabCut(image, gc_mask, None, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_MASK)
            
            # Convert to binary mask
            mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
            self.current_mask = mask
            
            # Display result
            mask_display = cv2.cvtColor(self.current_mask, cv2.COLOR_GRAY2RGB)
            self.seg_display.set_image(mask_display)
            self.seg_display.set_mode("view")
            self.seg_display_var.set("Mask")
            self.status_var.set(f"交互式分割完成 (使用 {mark_count} 个标记的并集)")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    # ============== Iterative GrabCut Methods ==============
    
    def _init_iterative_grabcut(self):
        """Initialize iterative GrabCut - draw rectangle"""
        try:
            if self.current_image is None:
                messagebox.showwarning("警告", "请先加载图像")
                return
            
            # Switch to IGC display
            if not self.igc_display_visible:
                self.seg_display.pack_forget()
                self.igc_display.pack(fill="both", expand=True)
                self.igc_display_visible = True
            
            # Set image and enable rectangle drawing
            self.igc_display.set_image(self.current_image)
            self.igc_display.set_stage(IterativeGrabCutDisplay.STAGE_INIT_RECT)
            self.status_var.set("在图像上拖拽绘制初始矩形（蓝色框），确保包含所有前景内容")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _first_grabcut(self):
        """Execute first GrabCut with rectangle"""
        try:
            if self.igc_display.image is None:
                raise ValueError("请先绘制矩形")
            
            if self.igc_display.init_rect is None:
                raise ValueError("请在图像上绘制矩形作为初始ROI")
            
            # Execute first GrabCut
            if self.igc_display.init_grabcut_with_rect():
                self.igc_display.set_stage(IterativeGrabCutDisplay.STAGE_MARKING)
                self.status_var.set("第一次分割完成。选择标注模式（前景红色/背景绿色）并在结果上标注")
            else:
                messagebox.showwarning("警告", "矩形过小，请重新绘制至少 10x10 像素的矩形")
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
            
            # Execute iterative GrabCut
            if self.igc_display.apply_grabcut_with_annotation():
                self.status_var.set("迭代分割完成。可继续标注进行微调，或点击\"应用分割结果\"保存")
            else:
                messagebox.showerror("错误", "GrabCut执行失败")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _apply_iterative_grabcut(self):
        """Apply iterative GrabCut result as final mask"""
        try:
            if self.igc_display.image is None or self.igc_display.gc_mask is None:
                raise ValueError("没有可应用的分割结果")
            
            # Save result to current_mask
            self.current_mask = self.igc_display.gc_mask.copy()
            
            # Switch back to normal display
            if self.igc_display_visible:
                self.igc_display.pack_forget()
                self.seg_display.pack(fill="both", expand=True)
                self.igc_display_visible = False
            
            # Display mask
            mask_display = cv2.cvtColor(self.current_mask, cv2.COLOR_GRAY2RGB)
            self.seg_display.set_image(mask_display)
            self.seg_display.set_mode("view")
            self.seg_display_var.set("Mask")
            self.status_var.set("迭代GrabCut分割已应用")
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
                messagebox.showwarning("警告", "请先执行应用Mask操作")
    
    def _segmentate_grabcut(self):
        """Apply GrabCut segmentation"""
        try:
            image = self.image_processor.current_image
            if image is None:
                raise ValueError("请先加载图像")
            
            h, w = image.shape[:2]
            x1, y1 = int(w * 0.2), int(h * 0.2)
            x2, y2 = int(w * 0.8), int(h * 0.8)
            
            mask = self.segmentation.grabcut_rect(image, x1, y1, x2, y2)
            self.current_mask = mask
            
            # Display original image
            self.seg_display.set_image(image)
            self.seg_display_var.set("原图")
            self.seg_display_label.config(text="原图")
            
            self.status_var.set("GrabCut分割完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _apply_threshold(self):
        """Apply threshold"""
        try:
            image = self.image_processor.current_image
            if image is None:
                raise ValueError("请先加载图像")
            
            threshold = int(self.threshold_spin.get())
            mask = self.segmentation.simple_threshold(image, threshold)
            self.current_mask = mask
            
            # Display
            self.seg_display.set_image(image)
            self.seg_display_var.set("原图")
            self.seg_display_label.config(text="原图")
            
            self.status_var.set("阈值分割完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _morph_open(self):
        """Morphological opening"""
        try:
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            kernel = int(self.kernel_spin.get())
            mask = self.segmentation.morph_open(self.current_mask, kernel)
            self.current_mask = mask
            
            mask_display = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
            self.seg_display.set_image(mask_display)
            self.seg_display_var.set("Mask")
            self.seg_display_label.config(text="Mask")
            self.status_var.set("开运算完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _morph_close(self):
        """Morphological closing"""
        try:
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            kernel = int(self.kernel_spin.get())
            mask = self.segmentation.morph_close(self.current_mask, kernel)
            self.current_mask = mask
            
            mask_display = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
            self.seg_display.set_image(mask_display)
            self.seg_display_var.set("Mask")
            self.seg_display_label.config(text="Mask")
            self.status_var.set("闭运算完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _apply_mask_to_image(self):
        """Apply mask: foreground keeps original color, background becomes white"""
        try:
            image = self.image_processor.current_image
            if not hasattr(self, 'current_mask') or self.current_mask is None:
                raise ValueError("请先执行分割")
            
            # Ensure image is RGB
            if len(image.shape) == 2:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                image_rgb = image.copy()
            
            # Convert mask to binary
            mask_binary = (self.current_mask > 127).astype(np.uint8) * 255
            
            # Apply mask: foreground keeps original color, background is white
            result = np.ones_like(image_rgb) * 255
            result[mask_binary == 255] = image_rgb[mask_binary == 255]
            
            # Store result and update display
            self.mask_applied_result = result.copy()
            self.seg_display.set_image(result)
            self.seg_display_var.set("Mask应用结果")
            self.seg_display_label.config(text="Mask应用结果")
            self.status_var.set("Mask已应用: 前景保留彩色，背景为白色")
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
    
    def _on_color_metric_changed(self, event=None):
        """Color metric (color space) changed"""
        metric_display_to_internal = {
            "加权距离": "weighted",
            "欧氏距离": "euclidean",
            "Lab色空": "lab",
            "CIE76": "ciede76"
        }
        selected = self.color_metric_var.get()
        metric = metric_display_to_internal.get(selected, "weighted")
        if self.color_manager:
            self.color_manager.set_color_metric(metric)
            self.status_var.set(f"色彩空间已切换: {selected}")
    
    def _generate_pattern(self):
        """Generate pattern"""
        def _generate():
            try:
                # Check if using mask result is requested but not available
                if self.use_mask_result_var.get():
                    if self.mask_applied_result is None:
                        raise ValueError("已勾选'使用Mask处理结果'，但还未执行Mask应用！\n请先在前景分割标签页执行Mask应用。")
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
                
                config = PatternConfig(
                    width_beads=w_val,
                    height_beads=h_val,
                    max_colors=color_limit
                )
                
                pattern, bom = self.pattern_generator.generate_pattern(
                    image,
                    self.color_manager.get_palette(),
                    config
                )
                
                self.current_pattern = pattern
                self.current_bom = bom

                self.pattern_display.set_image(pattern)
                self._update_bom_list(bom)

                self.status_var.set(f"图案生成成功: {w_val}x{h_val}, 使用{len(bom['colors'])}种颜色")

                # Auto-render with grid (default view fills full window)
                self.pattern_display.after(100, self._render_pattern_grid)
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
            
            bead_size = int(self.bead_size.get())
            rendered = self.pattern_generator.render_pattern_with_grid(bead_size)
            
            self.pattern_display.set_image(rendered)
            self.status_var.set("带网格渲染完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _render_pattern_codes(self):
        """Render with codes and grid"""
        try:
            pattern = self.pattern_generator.get_pattern()
            color_map = self.pattern_generator.get_color_map()

            if pattern is None or color_map is None:
                raise ValueError("请先生成图案")

            bead_size = int(self.bead_size.get())
            rendered = self.pattern_generator.render_pattern_with_codes_and_grid(bead_size)
            
            self.pattern_display.set_image(rendered)
            self.status_var.set("带编码渲染完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
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
            bead_size = int(self.bead_size.get())
            filename = self.export_filename.get() or f"{self.loaded_filename}_拼豆图纸"
            page_size = self.page_size.get()

            export_any = False
            export_paths = []

            # 预先渲染两个版本: 网格版(无编码) 和 编码+网格版
            rendered_grid = self.pattern_generator.render_pattern_with_grid(bead_size)
            rendered_codes_grid = self.pattern_generator.render_pattern_with_codes_and_grid(bead_size)

            if self.export_png_var.get():
                # PNG: 导出两张 — 网格版 + 编码网格版
                p1 = self.exporter.export_png(rendered_grid,
                    f"{filename}_grid", scale)
                export_paths.append(f"PNG网格版: {p1}")
                p2 = self.exporter.export_png(rendered_codes_grid,
                    f"{filename}_codes", scale)
                export_paths.append(f"PNG编码版: {p2}")
                export_any = True

            if self.export_pdf_var.get():
                # PDF: 使用带编码+网格的完整版本
                filepath = self.exporter.export_pdf(
                    rendered_codes_grid, bom, filename, page_size, title=filename)
                export_paths.append(f"PDF: {filepath}")
                export_any = True

            if self.export_bom_json_var.get():
                filepath = self.exporter.export_bom_json(bom, filename)
                export_paths.append(f"JSON物料清单: {filepath}")
                export_any = True

            if self.export_bom_csv_var.get():
                filepath = self.exporter.export_bom_csv(bom, filename)
                export_paths.append(f"CSV物料清单: {filepath}")
                export_any = True

            if not export_any:
                raise ValueError("请至少勾选一个导出格式")

            msg = "一键导出完成:\n" + "\n".join(export_paths)
            messagebox.showinfo("成功", msg)
            self.status_var.set("一键导出完成")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def _export_bom_csv(self):
        """Export BOM as CSV"""
        try:
            bom = self.pattern_generator.get_bom()
            if bom is None:
                raise ValueError("请先生成图案")
            
            filename = self.export_filename.get() or 'pattern'
            filepath = self.exporter.export_bom_csv(bom, filename)
            messagebox.showinfo("成功", f"已导出: {filepath}")
            self.status_var.set("BOM (CSV)导出完成")
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
