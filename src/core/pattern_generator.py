"""
Pattern generator for creating perler bead patterns
"""
import numpy as np
import cv2
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
import json


# Fraction to blend a masked-out bead's color toward white when rendering the
# standard chart (0.70 = keep ~30% of the color so the shape stays faintly
# visible while clearly washed out).
MASK_FADE = 0.70

# Standard-chart render resolution (pixels per bead cell). 30 keeps per-cell
# codes crisp and mitigates PDF upscale blur.
CHART_BEAD_PX = 30

# Supersample factor for the standard chart: render at Nx then LANCZOS down.
# 2 gives visibly crisper code text; set to 1 to disable.
CHART_SUPERSAMPLE = 2

# Above this many bead cells, drop supersampling to 1 to bound canvas memory.
CHART_SUPERSAMPLE_MAX_CELLS = 4000

# Preferred CJK font order for numeric codes (Microsoft YaHei's numerals read
# cleaner than SimHei at small sizes).
FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/SimHei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)


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
    icm_smooth: float = 0.0  # ICM spatial-coherence refinement (0=off)


class PatternGenerator:
    """Generates perler bead patterns from images"""
    
    def __init__(self):
        self.pattern = None
        self.color_map = None  # Maps pixel color to bead code
        self.bom = None  # Bill of materials
        self.config = None
        # bool (h_beads, w_beads): True = keep bead, False = masked out.
        # Attached externally (by the UI) after generate_pattern when the
        # image was processed with a mask; drives faded rendering on export.
        self.bead_mask = None

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
        # Reset any stale mask from a previous run; the UI re-attaches a fresh
        # bead_mask after this returns when the image was masked.
        self.bead_mask = None

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
            icm_smooth=config.icm_smooth,
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
    
    def render_standard_chart(self, bead_pixel_size: int = CHART_BEAD_PX, major_every: int = 5,
                              palette=None, bead_mask=None, fade_masked: bool = True,
                              supersample: int = CHART_SUPERSAMPLE,
                              mask_bg=None) -> np.ndarray:
        """
        Render a standard perler-bead chart (the exported/printed form).

        Layout:
          - bead cells filled with their color + per-cell color code
          - minor grid line every cell (light gray)
          - major grid line every `major_every` cells (bold dark) + coordinate
            tick number on the left + top (5, 10, 15, ...)
          - bottom BOM bar: for each used color a uniform rounded chip
            (color block + code on the left 2/5, bead count on the right 3/5),
            sorted by count descending, wrapped into aligned columns.

        Args:
            bead_pixel_size: Size of each bead cell in pixels
            major_every: Draw a major grid line / coordinate tick every N cells
            palette: ColorPalette for resolving swatch RGB/name (falls back to
                the pattern pixel color when a code cannot be resolved)
            bead_mask: Optional bool array (h_beads, w_beads), True = keep bead,
                False = masked out. Masked-out cells are faded toward white and
                their code text is omitted. Defaults to self.bead_mask.
            fade_masked: When False, ignore the mask entirely (full render).
            supersample: Render at Nx resolution then LANCZOS-downscale for
                crisper text (1 = off). Auto-disabled on very large grids.
            mask_bg: Optional (r,g,b) solid fill for masked-out cells instead of
                the white fade (e.g. (255,255,255) or (0,0,0)). The code text and
                BOM are skipped for masked cells either way.

        Returns:
            Rendered standard chart as an RGB ndarray
        """
        if self.color_map is None or self.pattern is None:
            raise ValueError("未生成图案")

        from PIL import Image, ImageDraw, ImageFont
        import os

        h, w = self.color_map.shape[:2]

        # Supersample: render everything at ss x resolution, downscale at the
        # end. All geometry derives from `cell`, so scaling it scales the whole
        # chart with zero coordinate edits.
        ss = max(1, int(supersample))
        if w * h > CHART_SUPERSAMPLE_MAX_CELLS:
            ss = 1
        cell = bead_pixel_size * ss

        # Resolve the bead-level mask (explicit param wins, else the attribute
        # attached by the UI). Guard on shape so a mismatched mask degrades to
        # no fade instead of crashing.
        bm = bead_mask if bead_mask is not None else self.bead_mask
        use_fade = fade_masked and bm is not None and getattr(bm, 'shape', None) == (h, w)

        # --- font (cleaner CJK first; cached by size to avoid per-cell reload) ---
        _font_cache = {}

        def _load_font(size):
            if size in _font_cache:
                return _font_cache[size]
            font = None
            for path in FONT_CANDIDATES:
                if os.path.exists(path):
                    try:
                        font = ImageFont.truetype(path, size)
                        break
                    except Exception:
                        pass
            if font is None:
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None
            _font_cache[size] = font
            return font

        # --- geometry ---
        left_margin = cell * 2 + 6   # room for 2-3 digit tick numbers on the left
        top_margin = cell + 10       # room for tick numbers on the top
        grid_w = w * cell
        grid_h = h * cell

        # usage-bar (BOM) metrics
        sw = cell                      # swatch size
        bar_font_size = max(10, int(cell * 0.7))
        bar_pad_x = cell // 2

        tick_font = _load_font(max(10, int(cell * 0.8)))
        bar_font = _load_font(bar_font_size)

        # measure usage-bar width requirement to decide row wrapping; when a
        # mask is active, count only the kept (foreground) beads so the BOM bar
        # excludes the masked-out background.
        usage = self._sorted_usage(palette, bead_mask=(bm if use_fade else None))

        # build swatch color lookup
        code_to_rgb = self._code_rgb_lookup(palette)

        # probe text widths for wrapping
        probe = Image.new("RGB", (10, 10))
        probe_draw = ImageDraw.Draw(probe)

        def text_width(s, font):
            if font is None:
                return len(s) * 8
            try:
                return font.getlength(s)
            except Exception:
                bbox = probe_draw.textbbox((0, 0), s, font=font)
                return bbox[2] - bbox[0]

        # --- uniform chip geometry (every chip identical size) ---
        # Left color block + code occupies the left 2/5, the count the right
        # 3/5. chip_w is solved from the 2:3 ratio so each half fits its longest
        # text with padding AND clears the rounded-corner arcs.
        pad_x = max(8, cell // 3)
        chip_h = max(sw + 2, bar_font_size + 10)
        radius = max(8, chip_h // 2)   # pill-like corners (fixes the bevel look)
        max_code_w = max((text_width(c, bar_font) for c, _ in usage), default=0)
        max_count_w = max((text_width(str(n), bar_font) for _, n in usage), default=0)
        # left (2/5) must hold code + 2*pad + left corner arc;
        # right (3/5) must hold count + 2*pad + right corner arc.
        need_left = (max_code_w + 2 * pad_x + radius) * 5 // 2
        need_right = (max_count_w + 2 * pad_x + radius) * 5 // 3
        chip_w = int(max(need_left, need_right))
        left_w = chip_w * 2 // 5
        right_w = chip_w - left_w
        gap = bar_pad_x
        bar_row_h = chip_h + max(6, cell // 3)   # row pitch tracks the chip height
        title_h = bar_row_h                       # room for the "BOM" label row

        # lay out chips into aligned columns within grid width (+ margins)
        bar_area_width = grid_w + left_margin + 6
        per_row = max(1, (bar_area_width + gap) // (chip_w + gap))
        rows = [usage[i:i + per_row] for i in range(0, len(usage), per_row)]

        bar_top = top_margin + grid_h + 14
        # total height: title row + one row per chip row + bottom padding
        bar_height = (title_h + len(rows) * bar_row_h) if rows else 0

        total_w = left_margin + grid_w + 8
        total_h = bar_top + bar_height + max(10, cell // 2)

        canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # --- bead cells ---
        for y in range(h):
            for x in range(w):
                code = str(self.color_map[y, x])
                rgb = code_to_rgb.get(code, tuple(int(c) for c in self.pattern[y, x][:3]))
                x1 = left_margin + x * cell
                y1 = top_margin + y * cell

                # masked-out cells: either fill a solid background (mask_bg) or
                # fade the fill toward white; either way skip the code + BOM.
                masked_out = use_fade and not bm[y, x]
                if masked_out:
                    if mask_bg is not None:
                        rgb = tuple(int(c) for c in mask_bg)
                    else:
                        rgb = tuple(int(round(c + (255 - c) * MASK_FADE)) for c in rgb)
                draw.rectangle([x1, y1, x1 + cell, y1 + cell], fill=rgb)

                if masked_out:
                    continue

                # per-cell code (adaptive, contrast-colored)
                lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                txt_color = (0, 0, 0) if lum > 128 else (255, 255, 255)
                cf = _load_font(max(9, int(cell * 0.43)))
                if cf is not None:
                    try:
                        tb = draw.textbbox((0, 0), code, font=cf)
                        tw, th = tb[2] - tb[0], tb[3] - tb[1]
                        draw.text((x1 + (cell - tw) / 2 - tb[0],
                                   y1 + (cell - th) / 2 - tb[1]),
                                  code, fill=txt_color, font=cf)
                    except Exception:
                        pass

        # --- grid lines (minor light, major bold) ---
        minor_color = (200, 200, 200)
        major_color = (90, 90, 90)
        minor_w = 1
        major_w = 3 if cell >= 16 else 2

        for xi in range(w + 1):
            x = left_margin + xi * cell
            major = (xi % major_every == 0)
            draw.line([x, top_margin, x, top_margin + grid_h],
                      fill=major_color if major else minor_color,
                      width=major_w if major else minor_w)
        for yi in range(h + 1):
            y = top_margin + yi * cell
            major = (yi % major_every == 0)
            draw.line([left_margin, y, left_margin + grid_w, y],
                      fill=major_color if major else minor_color,
                      width=major_w if major else minor_w)

        # --- coordinate ticks: left + top, every major_every ---
        if tick_font is not None:
            for xi in range(major_every, w + 1, major_every):
                x = left_margin + xi * cell
                s = str(xi)
                try:
                    tb = draw.textbbox((0, 0), s, font=tick_font)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    draw.text((x - tw / 2 - tb[0], top_margin - th - 4 - tb[1]),
                              s, fill=(40, 40, 40), font=tick_font)
                except Exception:
                    pass
            for yi in range(major_every, h + 1, major_every):
                y = top_margin + yi * cell
                s = str(yi)
                try:
                    tb = draw.textbbox((0, 0), s, font=tick_font)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    draw.text((left_margin - tw - 8 - tb[0], y - th / 2 - tb[1]),
                              s, fill=(40, 40, 40), font=tick_font)
                except Exception:
                    pass

        # --- bottom BOM bar (uniform rounded chips) ---
        if rows:
            # section label sits in the title row; chips start below it
            if bar_font is not None:
                try:
                    draw.text((left_margin, bar_top + 2), "BOM",
                              fill=(30, 30, 30), font=bar_font)
                except Exception:
                    pass
            yy = bar_top + title_h
            for row in rows:
                xx = left_margin
                for code, count in row:
                    rgb = code_to_rgb.get(code, (128, 128, 128))
                    # outer chip: white rounded rect with a thin black border
                    draw.rounded_rectangle([xx, yy, xx + chip_w, yy + chip_h],
                                           radius=radius, fill=(255, 255, 255),
                                           outline=(0, 0, 0), width=1)
                    # left color block (rounded left edge, squared right edge so
                    # the split is a straight divider line)
                    draw.rounded_rectangle([xx, yy, xx + left_w, yy + chip_h],
                                           radius=radius, fill=rgb)
                    draw.rectangle([xx + left_w - radius, yy, xx + left_w, yy + chip_h],
                                   fill=rgb)
                    # divider between the two halves
                    draw.line([xx + left_w, yy + 1, xx + left_w, yy + chip_h - 1],
                              fill=(0, 0, 0), width=1)
                    if bar_font is not None:
                        # code text centered in the left color block; white on dark fills
                        lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                        code_color = (0, 0, 0) if lum > 128 else (255, 255, 255)
                        try:
                            tb = draw.textbbox((0, 0), code, font=bar_font)
                            tw, th = tb[2] - tb[0], tb[3] - tb[1]
                            draw.text((xx + (left_w - tw) / 2 - tb[0],
                                       yy + (chip_h - th) / 2 - tb[1]),
                                      code, fill=code_color, font=bar_font)
                        except Exception:
                            pass
                        # count text centered in the right block (always dark);
                        # clamp so it never overlaps the chip's right corner arc
                        label = str(count)
                        try:
                            tb = draw.textbbox((0, 0), label, font=bar_font)
                            tw, th = tb[2] - tb[0], tb[3] - tb[1]
                            cx = xx + left_w + (right_w - tw) / 2 - tb[0]
                            cx = min(cx, xx + chip_w - radius - tw - tb[0])
                            draw.text((cx, yy + (chip_h - th) / 2 - tb[1]),
                                      label, fill=(20, 20, 20), font=bar_font)
                        except Exception:
                            pass
                    xx += chip_w + gap
                yy += bar_row_h

        if ss > 1:
            canvas = canvas.resize((max(1, total_w // ss), max(1, total_h // ss)),
                                   Image.LANCZOS)
        return np.array(canvas, dtype=np.uint8)

    def _sorted_usage(self, palette=None, bead_mask=None) -> List[Tuple[str, int]]:
        """Return [(code, count)] sorted by count desc.

        When a valid bead_mask is available, count only the kept (foreground)
        cells so masked-out background beads are excluded; otherwise fall back
        to the bom counts, else tally the color_map directly."""
        bm = bead_mask if bead_mask is not None else self.bead_mask
        if bm is not None and self.color_map is not None and \
                getattr(bm, 'shape', None) == self.color_map.shape:
            counts = {}
            for y in range(bm.shape[0]):
                for x in range(bm.shape[1]):
                    if bm[y, x]:
                        c = str(self.color_map[y, x])
                        counts[c] = counts.get(c, 0) + 1
            items = list(counts.items())
        elif self.bom is not None and 'colors' in self.bom:
            items = [(code, info['count']) for code, info in self.bom['colors'].items()]
        else:
            counts = {}
            for row in self.color_map:
                for c in row:
                    counts[str(c)] = counts.get(str(c), 0) + 1
            items = list(counts.items())
        items.sort(key=lambda kv: (-kv[1], kv[0]))
        return items

    def rebuild_bom_with_mask(self, bead_mask, palette) -> Dict:
        """Rebuild the BOM counting only kept (foreground) beads so the BOM
        excludes masked-out background. Same structure as _create_bom."""
        usage = self._sorted_usage(palette, bead_mask=bead_mask)
        total = sum(c for _, c in usage)
        bom = {'total_beads': total, 'colors': {}}
        for code, count in usage:
            color = palette.get_color(code) if palette is not None else None
            bom['colors'][code] = {
                'name': color.name if color else code,
                'hex': color.hex if color else '#000000',
                'count': count,
                'percentage': (count / total * 100) if total else 0.0,
            }
        self.bom = bom
        return bom

    def _code_rgb_lookup(self, palette=None) -> Dict[str, Tuple[int, int, int]]:
        """Map color code -> RGB tuple for swatch fills."""
        lookup = {}
        if palette is not None and getattr(palette, 'colors', None):
            for c in palette.colors:
                lookup[str(c.code)] = tuple(int(v) for v in c.rgb[:3])
        # fill any missing codes from the pattern itself
        if self.pattern is not None and self.color_map is not None:
            for y in range(self.color_map.shape[0]):
                for x in range(self.color_map.shape[1]):
                    code = str(self.color_map[y, x])
                    if code not in lookup:
                        lookup[code] = tuple(int(v) for v in self.pattern[y, x][:3])
        return lookup

    @staticmethod
    def _is_light_color(rgb: np.ndarray) -> bool:
        """Determine if color is light or dark"""
        r, g, b = rgb[:3]
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance > 128


if __name__ == '__main__':
    generator = PatternGenerator()
    print("PatternGenerator ready")
