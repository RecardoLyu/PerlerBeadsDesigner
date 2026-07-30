"""
Pattern generator for creating perler bead patterns
"""
import numpy as np
import cv2
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
import json


@dataclass
class PatternConfig:
    """Configuration for pattern generation"""
    width_beads: int  # Width in beads
    height_beads: int  # Height in beads
    max_colors: Optional[int] = None  # None = use all colors
    dpi: int = 300  # Resolution for output
    bead_size_mm: float = 5.0  # Physical size of one bead in mm
    allow_color_mixing: bool = False  # Whether to mix colors for better results
    salience_strength: float = 1.0  # Detail-preservation weight (0-2)
    dither: bool = False  # Floyd-Steinberg error diffusion
    dither_strength: float = 1.0  # Error-diffusion strength (0-1)


class PatternGenerator:
    """Generates perler bead patterns from images"""
    
    def __init__(self):
        self.pattern = None
        self.color_map = None  # Maps pixel color to bead code
        self.bom = None  # Bill of materials
        self.config = None
    
    def generate_pattern(self, image: np.ndarray, palette,
                        config: PatternConfig, color_manager=None) -> Tuple[np.ndarray, Dict]:
        """
        Generate pattern from image

        Args:
            image: Input image (RGB)
            palette: ColorPalette instance (used for color map / BOM)
            config: PatternConfig for generation
            color_manager: ColorManager for quantization (preferred). If None,
                falls back to a temporary ColorManager built around palette.

        Returns:
            Tuple of (pattern array, bill of materials)
        """
        self.config = config

        # Ensure image is RGB
        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError("请提供RGB格式的图像")

        # Resize to bead dimensions. INTER_AREA (box average) downscales with
        # far less moiré/transition-color bleeding than INTER_LINEAR, which is
        # what produced the grid-like artifacts at high color limits.
        resized = cv2.resize(image, (config.width_beads, config.height_beads),
                            interpolation=cv2.INTER_AREA)

        # Quantize via ColorManager (salience-weighted when max_colors set)
        if color_manager is None:
            from .color_manager import ColorManager
            color_manager = ColorManager()
            color_manager.palette = palette

        quantized, color_usage = color_manager.quantize_image(
            resized,
            color_limit=config.max_colors,
            salience_strength=config.salience_strength,
            dither=config.dither,
            dither_strength=config.dither_strength,
        )

        # Create pattern with color codes
        self.pattern = quantized.copy()
        self.color_map = self._create_color_map(quantized, palette)
        self.bom = self._create_bom(color_usage, palette)

        return self.pattern.copy(), self.bom
    
    def _create_color_map(self, pattern: np.ndarray, palette) -> np.ndarray:
        """Create map of color codes for each pixel"""
        h, w = pattern.shape[:2]
        color_map = np.empty((h, w), dtype=object)

        pixels = pattern.reshape(-1, 3)
        idx = palette.get_closest_indices_batch(pixels)
        codes = [palette.colors[i].code for i in idx]
        color_map = np.array(codes, dtype=object).reshape(h, w)

        return color_map
    
    def _create_bom(self, color_usage: Dict, palette) -> Dict:
        """Create Bill of Materials"""
        bom = {
            'total_beads': sum(color_usage.values()),
            'colors': {}
        }
        
        for code, count in sorted(color_usage.items()):
            color = palette.get_color(code)
            if color:
                bom['colors'][code] = {
                    'name': color.name,
                    'hex': color.hex,
                    'count': count,
                    'percentage': 0.0
                }
        
        # Calculate percentages
        total = bom['total_beads']
        for code in bom['colors']:
            bom['colors'][code]['percentage'] = (bom['colors'][code]['count'] / total * 100)
        
        return bom
    
    def get_pattern(self) -> Optional[np.ndarray]:
        """Get current pattern"""
        return self.pattern.copy() if self.pattern is not None else None
    
    def get_bom(self) -> Optional[Dict]:
        """Get bill of materials"""
        return self.bom.copy() if self.bom is not None else None
    
    def get_color_map(self) -> Optional[np.ndarray]:
        """Get color code map"""
        return self.color_map.copy() if self.color_map is not None else None
    
    def render_pattern_image(self, bead_pixel_size: int = 10) -> np.ndarray:
        """
        Render pattern as displayable image
        
        Args:
            bead_pixel_size: Size of each bead in pixels
        
        Returns:
            Rendered pattern image
        """
        if self.pattern is None:
            raise ValueError("未生成图案")
        
        h, w = self.pattern.shape[:2]
        output = np.zeros((h * bead_pixel_size, w * bead_pixel_size, 3), dtype=np.uint8)
        
        for y in range(h):
            for x in range(w):
                color = self.pattern[y, x]
                y1 = y * bead_pixel_size
                y2 = y1 + bead_pixel_size
                x1 = x * bead_pixel_size
                x2 = x1 + bead_pixel_size
                output[y1:y2, x1:x2] = color
        
        return output
    
    def render_pattern_with_grid(self, bead_pixel_size: int = 10, 
                                grid_color: Tuple[int, int, int] = (200, 200, 200),
                                grid_width: int = 1) -> np.ndarray:
        """
        Render pattern with grid overlay
        
        Args:
            bead_pixel_size: Size of each bead in pixels
            grid_color: RGB color of grid
            grid_width: Width of grid lines (note: uses thinner lines for better boundary visibility)
        
        Returns:
            Rendered pattern with grid
        """
        if self.pattern is None:
            raise ValueError("未生成图案")
            
        h, w = self.pattern.shape[:2]
        image = np.zeros((h * bead_pixel_size, w * bead_pixel_size, 3), dtype=np.uint8)
        
        # Fill with bead colors
        for y in range(h):
            for x in range(w):
                color = self.pattern[y, x]
                y1 = y * bead_pixel_size
                y2 = y1 + bead_pixel_size
                x1 = x * bead_pixel_size
                x2 = x1 + bead_pixel_size
                image[y1:y2, x1:x2] = color
        
        # Draw vertical grid lines (at bead boundaries)
        # Use grid_width=1 for crisp boundaries regardless of bead size
        actual_grid_width = max(1, min(grid_width, bead_pixel_size // 10 + 1))
        for x in range(w + 1):
            x_pixel = x * bead_pixel_size
            cv2.line(image, (x_pixel, 0), (x_pixel, image.shape[0]), grid_color, actual_grid_width)
        
        # Draw horizontal grid lines (at bead boundaries)
        for y in range(h + 1):
            y_pixel = y * bead_pixel_size
            cv2.line(image, (0, y_pixel), (image.shape[1], y_pixel), grid_color, actual_grid_width)
        
        return image
    
    def render_pattern_with_codes(self, bead_pixel_size: int = 20) -> np.ndarray:
        """
        Render pattern with color codes labeled
        
        Args:
            bead_pixel_size: Size of each bead in pixels
        
        Returns:
            Rendered pattern with codes
        """
        if self.color_map is None or self.pattern is None:
            raise ValueError("未生成色彩映射")
        
        h, w = self.color_map.shape[:2]
        output = np.ones((h * bead_pixel_size, w * bead_pixel_size, 3), dtype=np.uint8) * 255
        
        # Calculate font scale based on bead pixel size
        # Smaller beads (10-15px) use font_scale ~0.3
        # Larger beads (50-100px) use font_scale ~1.5-2.0
        if bead_pixel_size <= 10:
            font_scale = 0.2
        elif bead_pixel_size <= 20:
            font_scale = 0.3
        elif bead_pixel_size <= 30:
            font_scale = 0.5
        elif bead_pixel_size <= 50:
            font_scale = 0.8
        else:
            font_scale = 1.0 + (bead_pixel_size - 50) / 50.0  # Scale up for larger beads
        
        for y in range(h):
            for x in range(w):
                try:
                    color_code = str(self.color_map[y, x])
                    color = self.pattern[y, x]

                    y1 = y * bead_pixel_size
                    y2 = y1 + bead_pixel_size
                    x1 = x * bead_pixel_size
                    x2 = x1 + bead_pixel_size

                    # Draw color square
                    output[y1:y2, x1:x2] = color

                    # Draw code text with adaptive scaling to avoid overflow for 3-char codes
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    thickness = max(1, int(bead_pixel_size / 20))

                    # Determine text color based on background brightness
                    if len(color) >= 3:
                        r, g, b = int(color[0]), int(color[1]), int(color[2])
                    else:
                        r = g = b = 128

                    luminance = 0.299 * r + 0.587 * g + 0.114 * b
                    text_color = (0, 0, 0) if luminance > 128 else (255, 255, 255)

                    # Adaptive font scale per cell
                    max_text_width = bead_pixel_size - 4
                    max_text_height = bead_pixel_size - 4

                    # Start from base font_scale and reduce if needed
                    fs = font_scale
                    ts = cv2.getTextSize(color_code, font, fs, thickness)[0]
                    if ts[0] > max_text_width or ts[1] > max_text_height:
                        # Compute width and height ratios and pick the smaller
                        scale_w = max_text_width / ts[0] if ts[0] > 0 else 1.0
                        scale_h = max_text_height / ts[1] if ts[1] > 0 else 1.0
                        fs = max(0.1, fs * min(scale_w, scale_h))
                        ts = cv2.getTextSize(color_code, font, fs, thickness)[0]

                    text_x = x1 + max(1, (bead_pixel_size - ts[0]) // 2)
                    text_y = y1 + max(1, (bead_pixel_size + ts[1]) // 2)

                    cv2.putText(output, color_code, (text_x, text_y), font, fs, text_color, thickness)
                except Exception:
                    continue
        
        return output
    
    def render_pattern_with_codes_and_grid(self, bead_pixel_size: int = 20,
                                          grid_color: Tuple[int, int, int] = (200, 200, 200),
                                          grid_width: int = 1) -> np.ndarray:
        """
        Render pattern with both color codes and grid overlay
        
        Args:
            bead_pixel_size: Size of each bead in pixels
            grid_color: RGB color of grid lines
            grid_width: Width of grid lines
        
        Returns:
            Rendered pattern with codes and grid
        """
        if self.color_map is None or self.pattern is None:
            raise ValueError("未生成色彩映射")
        
        h, w = self.color_map.shape[:2]
        output = np.ones((h * bead_pixel_size, w * bead_pixel_size, 3), dtype=np.uint8) * 255
        
        # Calculate font scale based on bead pixel size
        if bead_pixel_size <= 10:
            font_scale = 0.2
        elif bead_pixel_size <= 20:
            font_scale = 0.3
        elif bead_pixel_size <= 30:
            font_scale = 0.5
        elif bead_pixel_size <= 50:
            font_scale = 0.8
        else:
            font_scale = 1.0 + (bead_pixel_size - 50) / 50.0
        
        # Draw beads with codes
        for y in range(h):
            for x in range(w):
                try:
                    color_code = str(self.color_map[y, x])
                    color = self.pattern[y, x]

                    y1 = y * bead_pixel_size
                    y2 = y1 + bead_pixel_size
                    x1 = x * bead_pixel_size
                    x2 = x1 + bead_pixel_size

                    # Draw color square
                    output[y1:y2, x1:x2] = color

                    # Draw code text with adaptive scaling to avoid overflow for multi-char codes
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    thickness = max(1, int(bead_pixel_size / 20))

                    # Determine text color based on background brightness
                    if len(color) >= 3:
                        r, g, b = int(color[0]), int(color[1]), int(color[2])
                    else:
                        r = g = b = 128

                    luminance = 0.299 * r + 0.587 * g + 0.114 * b
                    text_color = (0, 0, 0) if luminance > 128 else (255, 255, 255)

                    # Adaptive font scale per cell
                    max_text_width = bead_pixel_size - 4
                    max_text_height = bead_pixel_size - 4

                    fs = font_scale
                    ts = cv2.getTextSize(color_code, font, fs, thickness)[0]
                    if ts[0] > max_text_width or ts[1] > max_text_height:
                        scale_w = max_text_width / ts[0] if ts[0] > 0 else 1.0
                        scale_h = max_text_height / ts[1] if ts[1] > 0 else 1.0
                        fs = max(0.1, fs * min(scale_w, scale_h))
                        ts = cv2.getTextSize(color_code, font, fs, thickness)[0]

                    text_x = x1 + max(1, (bead_pixel_size - ts[0]) // 2)
                    text_y = y1 + max(1, (bead_pixel_size + ts[1]) // 2)

                    cv2.putText(output, color_code, (text_x, text_y), font, fs, text_color, thickness)
                except Exception:
                    continue
        
        # Draw vertical grid lines (on top of codes)
        for x in range(w + 1):
            x_pixel = x * bead_pixel_size
            cv2.line(output, (x_pixel, 0), (x_pixel, output.shape[0]), grid_color, grid_width)
        
        # Draw horizontal grid lines (on top of codes)
        for y in range(h + 1):
            y_pixel = y * bead_pixel_size
            cv2.line(output, (0, y_pixel), (output.shape[1], y_pixel), grid_color, grid_width)
        
        return output
    
    @staticmethod
    def _is_light_color(rgb: np.ndarray) -> bool:
        """Determine if color is light or dark"""
        r, g, b = rgb[:3]
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance > 128


if __name__ == '__main__':
    generator = PatternGenerator()
    print("PatternGenerator ready")
