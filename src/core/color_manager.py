"""
Color management for Perler beads
"""
import json
import os
from typing import List, Dict, Tuple
from pathlib import Path
import colorsys
import numpy as np
import cv2


class Color:
    """Represents a single perler bead color"""

    def __init__(self, code: str, name: str, hex_value: str):
        self.code = code
        self.name = name
        self.hex = hex_value
        self.rgb = self._hex_to_rgb(hex_value)

    @staticmethod
    def _hex_to_rgb(hex_value: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_value = hex_value.lstrip('#')
        return tuple(int(hex_value[i:i+2], 16) for i in (0, 2, 4))

    def rgb_normalized(self) -> Tuple[float, float, float]:
        """Return RGB values normalized to 0-1"""
        return tuple(c / 255.0 for c in self.rgb)

    @property
    def bgr(self) -> Tuple[int, int, int]:
        """Return BGR tuple for OpenCV"""
        return (self.rgb[2], self.rgb[1], self.rgb[0])

    @staticmethod
    def _rgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Convert RGB to CIE LAB color space"""
        rgb_array = np.uint8([[rgb]])
        lab_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2Lab)
        lab_values = tuple(float(x) for x in lab_array[0, 0])
        return lab_values

    def distance_to(self, other_rgb: Tuple[int, int, int],
                   metric: str = "weighted") -> float:
        """
        Calculate distance to another RGB color using specified metric

        Args:
            other_rgb: RGB tuple to compare
            metric: 'weighted' (default), 'euclidean', 'lab', 'ciede76'

        Returns:
            Distance value
        """
        if metric == "euclidean":
            return self._distance_euclidean(other_rgb)
        elif metric in ("lab", "ciede76"):
            return self._distance_lab(other_rgb)
        elif metric == "weighted":
            return self._distance_weighted(other_rgb)
        else:
            return self._distance_weighted(other_rgb)

    def _distance_weighted(self, other_rgb: Tuple[int, int, int]) -> float:
        """Weighted Euclidean distance (human perception based)"""
        r, g, b = self.rgb
        or_, og, ob = other_rgb

        dr = (r - or_) / 255.0
        dg = (g - og) / 255.0
        db = (b - ob) / 255.0

        # Formula: sqrt(3*dR^2 + 6*dG^2 + 1*dB^2)  (luminance-weighted)
        dist = ((3 * dr * dr) + (6 * dg * dg) + (1 * db * db)) ** 0.5
        return dist * 255

    def _distance_euclidean(self, other_rgb: Tuple[int, int, int]) -> float:
        """Simple Euclidean distance in RGB space"""
        r, g, b = self.rgb
        or_, og, ob = other_rgb
        return ((r - or_) ** 2 + (g - og) ** 2 + (b - ob) ** 2) ** 0.5

    def _distance_lab(self, other_rgb: Tuple[int, int, int]) -> float:
        """Distance in CIE LAB color space"""
        try:
            lab1 = self._rgb_to_lab(self.rgb)
            lab2 = self._rgb_to_lab(other_rgb)

            dl = lab1[0] - lab2[0]
            da = lab1[1] - lab2[1]
            db = lab1[2] - lab2[2]

            return (dl * dl + da * da + db * db) ** 0.5
        except:
            return self._distance_weighted(other_rgb)

    def _distance_ciede76(self, other_rgb: Tuple[int, int, int]) -> float:
        """CIE76 delta E distance in LAB color space (delegates to _distance_lab)"""
        return self._distance_lab(other_rgb)


class ColorPalette:
    """Manages a palette of perler bead colors"""

    def __init__(self, colors: List[Color] = None, color_metric: str = "weighted"):
        self.colors = colors or []
        self._color_dict = {c.code: c for c in self.colors}
        self.color_metric = color_metric
        self._closest_cache: Dict[Tuple[int, int, int], Color] = {}

    def add_color(self, color: Color):
        """Add a color to the palette"""
        self.colors.append(color)
        self._color_dict[color.code] = color

    def set_color_metric(self, metric: str):
        """Set the color distance metric"""
        valid_metrics = ['weighted', 'euclidean', 'lab', 'ciede76']
        if metric in valid_metrics:
            self.color_metric = metric
            self._closest_cache.clear()

    def get_color(self, code: str) -> Color:
        """Get color by code"""
        return self._color_dict.get(code)

    def get_closest_color(self, rgb: Tuple[int, int, int]) -> Color:
        """Find the closest color in the palette to the given RGB value"""
        if not self.colors:
            raise ValueError("调色板为空")

        if rgb in self._closest_cache:
            return self._closest_cache[rgb]

        closest = self.colors[0]
        min_distance = closest.distance_to(rgb, metric=self.color_metric)

        for color in self.colors[1:]:
            distance = color.distance_to(rgb, metric=self.color_metric)
            if distance < min_distance:
                min_distance = distance
                closest = color

        self._closest_cache[rgb] = closest
        return closest

    def to_dict(self) -> List[Dict]:
        """Convert palette to list of dictionaries"""
        return [
            {
                'code': c.code,
                'name': c.name,
                'hex': c.hex
            }
            for c in self.colors
        ]

    @staticmethod
    def from_dict(data: List[Dict]) -> 'ColorPalette':
        """Create palette from list of dictionaries"""
        colors = [Color(d['code'], d['name'], d['hex']) for d in data]
        return ColorPalette(colors)

    def save_to_json(self, filepath: str):
        """Save palette to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_from_json(filepath: str) -> 'ColorPalette':
        """Load palette from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ColorPalette.from_dict(data)


class ColorManager:
    """Main color management system"""

    def __init__(self, colors_file: str = None, color_metric: str = "weighted"):
        self.colors_file = colors_file
        self.palette = None
        self.color_metric = color_metric
        self._load_or_create_palette()

    def _load_or_create_palette(self):
        """Load palette from file or create default with fallback"""
        if self.colors_file:
            try:
                if os.path.exists(self.colors_file):
                    self.palette = ColorPalette.load_from_json(self.colors_file)
                    self.palette.set_color_metric(self.color_metric)
                    print(f"成功加载颜色表: {self.colors_file} ({len(self.palette.colors)} 种颜色)")
                else:
                    print(f"颜色表文件不存在: {self.colors_file}，使用默认颜色库")
                    self._create_default_palette()
            except Exception as e:
                print(f"加载颜色表出错 ({e})，使用默认颜色库")
                self._create_default_palette()
        else:
            self._create_default_palette()

    def _create_default_palette(self):
        """Create default palette with real MARD 221-color subset"""
        default_colors = [
            Color('H1', '纯白', '#ffffff'),
            Color('H7', '纯黑', '#010101'),
            Color('F5', '深红', '#e10328'),
            Color('B4', '翠绿', '#5fdf34'),
            Color('C8', '深蓝', '#0f52bd'),
            Color('A3', '柠檬黄', '#fcff92'),
            Color('H3', '浅灰', '#b4b4b4'),
            Color('H5', '深灰', '#464648'),
            Color('A7', '橙橘', '#fa8c4f'),
            Color('D7', '深紫', '#8758a9'),
            Color('E6', '玫红', '#eb4172'),
            Color('G7', '深棕', '#985c3a'),
            Color('C13', '淡蓝', '#cde7fe'),
            Color('B6', '薄荷绿', '#64e0a4'),
            Color('F2', '正红', '#f63d4b'),
            Color('E4', '桃红', '#e8649e'),
            Color('G3', '肤色', '#f1c4a5'),
            Color('M4', '浅卡其', '#e0d4bc'),
        ]
        self.palette = ColorPalette(default_colors, color_metric=self.color_metric)

    def get_palette(self) -> ColorPalette:
        """Get the current color palette"""
        return self.palette

    def set_color_metric(self, metric: str):
        """Set the color distance metric"""
        if self.palette:
            self.palette.set_color_metric(metric)
        self.color_metric = metric

    def get_color_metric(self) -> str:
        """Get the current color distance metric"""
        return self.color_metric if self.palette else "weighted"

    def update_from_remote(self, colors_data: List[Dict]):
        """Update palette from remote data"""
        self.palette = ColorPalette.from_dict(colors_data)
        self.palette.set_color_metric(self.color_metric)
        if self.colors_file:
            self.palette.save_to_json(self.colors_file)

    def quantize_image(self, image_array: np.ndarray, color_limit: int = None) -> Tuple[np.ndarray, Dict]:
        """Quantize image to palette colors"""
        if image_array.dtype != np.uint8:
            image_array = (image_array * 255).astype(np.uint8)

        h, w, c = image_array.shape if len(image_array.shape) == 3 else (image_array.shape[0], image_array.shape[1], 3)

        pixels = image_array.reshape(-1, 3) if c == 3 else image_array

        output = np.zeros_like(pixels)
        color_usage = {}

        for i, pixel in enumerate(pixels):
            closest = self.palette.get_closest_color(tuple(pixel))
            code = closest.code
            output[i] = closest.rgb
            color_usage[code] = color_usage.get(code, 0) + 1

        output = output.reshape(h, w, 3)

        if color_limit and len(color_usage) > color_limit:
            sorted_colors = sorted(color_usage.items(), key=lambda x: x[1], reverse=True)
            top_colors = set([code for code, _ in sorted_colors[:color_limit]])

            filtered_usage = {}
            for code, count in sorted_colors[:color_limit]:
                filtered_usage[code] = count

            new_palette = ColorPalette([self.palette.get_color(code) for code in top_colors])
            temp_palette = self.palette
            self.palette = new_palette

            output = np.zeros_like(pixels)
            filtered_usage = {}
            for i, pixel in enumerate(pixels):
                closest = self.palette.get_closest_color(tuple(pixel))
                code = closest.code
                output[i] = closest.rgb
                filtered_usage[code] = filtered_usage.get(code, 0) + 1

            output = output.reshape(h, w, 3)
            self.palette = temp_palette
            color_usage = filtered_usage

        return output.astype(np.uint8), color_usage


if __name__ == '__main__':
    manager = ColorManager()
    palette = manager.get_palette()
    print(f"调色板包含 {len(palette.colors)} 种颜色")
    for color in palette.colors[:5]:
        print(f"{color.code}: {color.name} {color.hex}")
