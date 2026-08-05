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

    def __init__(self, code: str, name: str, hex_value: str, lab: Tuple[float, float, float] = None):
        self.code = code
        self.name = name
        self.hex = hex_value
        self.rgb = self._hex_to_rgb(hex_value)
        # Optional measured CIE LAB (L 0-100, a/b -128~127). When provided it
        # is used instead of computing from hex, improving match accuracy.
        self.lab = tuple(lab) if lab is not None else None

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
        """Convert RGB to standardized CIE LAB color space
        (L: 0-100, a: -128~127, b: -128~127)"""
        rgb_array = np.uint8([[rgb]])
        lab_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2Lab)
        # OpenCV LAB output: L 0-255, a 0-255, b 0-255
        # Standardize to: L 0-100, a -128~127, b -128~127
        L = lab_array[0, 0, 0] * 100.0 / 255.0
        a = float(lab_array[0, 0, 1]) - 128.0
        b = float(lab_array[0, 0, 2]) - 128.0
        return (L, a, b)

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
        elif metric == "ciede2000":
            return self._distance_ciede2000(other_rgb)
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

    def _distance_ciede2000(self, other_rgb: Tuple[int, int, int]) -> float:
        """CIEDE2000 delta E distance (perceptually most accurate)"""
        try:
            lab1 = np.array(self._rgb_to_lab(self.rgb), dtype=np.float64)
            lab2 = np.array(self._rgb_to_lab(other_rgb), dtype=np.float64)
            return float(_ciede2000(lab1[None, :], lab2[None, :])[0, 0])
        except Exception:
            return self._distance_lab(other_rgb)


def _ciede2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """Vectorized CIEDE2000 between two LAB arrays.

    Args:
        lab1: (N,3) array
        lab2: (M,3) array
    Returns:
        (N,M) delta-E matrix
    """
    L1 = lab1[:, 0][:, None]
    a1 = lab1[:, 1][:, None]
    b1 = lab1[:, 2][:, None]
    L2 = lab2[:, 0][None, :]
    a2 = lab2[:, 1][None, :]
    b2 = lab2[:, 2][None, :]

    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0
    G = 0.5 * (1 - np.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
    a1p = a1 * (1 + G)
    a2p = a2 * (1 + G)
    C1p = np.hypot(a1p, b1)
    C2p = np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360

    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))

    Lbp = (L1 + L2) / 2.0
    Cbp = (C1p + C2p) / 2.0
    hsum = h1p + h2p
    hab = np.where(np.abs(h1p - h2p) > 180, (hsum + 360) / 2, hsum / 2)

    T = (1 - 0.17 * np.cos(np.radians(hab - 30))
         + 0.24 * np.cos(np.radians(2 * hab))
         + 0.32 * np.cos(np.radians(3 * hab + 6))
         - 0.20 * np.cos(np.radians(4 * hab - 63)))
    dtheta = 30 * np.exp(-(((hab - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc

    dE = np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                 + Rt * (dCp / Sc) * (dHp / Sh))
    return dE


class ColorPalette:
    """Manages a palette of perler bead colors"""

    def __init__(self, colors: List[Color] = None, color_metric: str = "weighted"):
        self.colors = colors or []
        self._color_dict = {c.code: c for c in self.colors}
        self.color_metric = color_metric
        self._closest_cache: Dict[Tuple[int, int, int], Color] = {}
        self._rebuild_matrices()

    def _rebuild_matrices(self):
        """Precompute palette RGB and LAB matrices for vectorized matching"""
        if self.colors:
            self._palette_rgb = np.array([c.rgb for c in self.colors], dtype=np.uint8)
            computed = cv2.cvtColor(self._palette_rgb.reshape(1, -1, 3), cv2.COLOR_RGB2Lab).reshape(-1, 3).astype(np.float64)
            computed[:, 0] = computed[:, 0] * 100.0 / 255.0
            computed[:, 1] = computed[:, 1] - 128.0
            computed[:, 2] = computed[:, 2] - 128.0
            # Prefer a measured LAB value when a color provides one.
            lab = computed.copy()
            for i, c in enumerate(self.colors):
                if c.lab is not None:
                    lab[i] = np.asarray(c.lab, dtype=np.float64)
            self._palette_lab = lab
        else:
            self._palette_rgb = np.zeros((0, 3), dtype=np.uint8)
            self._palette_lab = np.zeros((0, 3), dtype=np.float64)

    def add_color(self, color: Color):
        """Add a color to the palette"""
        self.colors.append(color)
        self._color_dict[color.code] = color
        self._rebuild_matrices()

    def set_color_metric(self, metric: str):
        """Set the color distance metric"""
        valid_metrics = ['weighted', 'euclidean', 'lab', 'ciede76', 'ciede2000']
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

    def get_closest_indices_batch(self, rgb_array: np.ndarray, metric: str = None) -> np.ndarray:
        """Vectorized nearest-color lookup for a batch of pixels.

        Args:
            rgb_array: (N,3) uint8 array of RGB pixels
            metric: distance metric (defaults to palette's color_metric)
        Returns:
            (N,) int array of palette indices
        """
        metric = metric or self.color_metric
        if not self.colors:
            raise ValueError("调色板为空")
        pix = rgb_array.astype(np.float64)
        P = self._palette_rgb.astype(np.float64)

        if metric == "euclidean":
            d = ((pix[:, None, :] - P[None, :, :]) ** 2).sum(-1)
        elif metric == "weighted":
            dr = (pix[:, 0][:, None] - P[:, 0][None, :]) / 255.0
            dg = (pix[:, 1][:, None] - P[:, 1][None, :]) / 255.0
            db = (pix[:, 2][:, None] - P[:, 2][None, :]) / 255.0
            d = 3 * dr * dr + 6 * dg * dg + 1 * db * db
        elif metric == "ciede2000":
            lab = self._rgb_batch_to_lab(rgb_array)
            d = _ciede2000(lab, self._palette_lab)
        else:  # lab / ciede76
            lab = self._rgb_batch_to_lab(rgb_array)
            d = ((lab[:, None, :] - self._palette_lab[None, :, :]) ** 2).sum(-1)
        return d.argmin(axis=1)

    @staticmethod
    def _rgb_batch_to_lab(rgb_array: np.ndarray) -> np.ndarray:
        """(N,3) uint8 RGB -> standardized LAB (L 0-100, a/b -128~127)"""
        arr = rgb_array.reshape(-1, 1, 3).astype(np.uint8)
        lab = cv2.cvtColor(arr, cv2.COLOR_RGB2Lab).reshape(-1, 3).astype(np.float64)
        lab[:, 0] = lab[:, 0] * 100.0 / 255.0
        lab[:, 1] = lab[:, 1] - 128.0
        lab[:, 2] = lab[:, 2] - 128.0
        return lab

    def to_dict(self) -> List[Dict]:
        """Convert palette to list of dictionaries"""
        out = []
        for c in self.colors:
            d = {'code': c.code, 'name': c.name, 'hex': c.hex}
            if c.lab is not None:
                d['lab'] = [round(float(v), 3) for v in c.lab]
            out.append(d)
        return out

    @staticmethod
    def from_dict(data: List[Dict]) -> 'ColorPalette':
        """Create palette from list of dictionaries (optional 'lab' = measured LAB)"""
        colors = [Color(d['code'], d['name'], d['hex'], lab=d.get('lab')) for d in data]
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

    # 支持的拼豆品牌：key -> (显示名, palette 目录下的文件名)
    # 数据来自 GitHub maxcleme/beadcolors（真实色号+RGB，转 {code,name,hex}）。
    BRANDS = {
        'mard':     ('MARD',           'mard.json'),
        'perler':   ('Perler',         'perler.json'),
        'hama':     ('Hama',           'hama.json'),
        'artkal_s': ('Artkal S-5mm',   'artkal_s.json'),
        'artkal_c': ('Artkal C-2.6mm', 'artkal_c.json'),
    }

    def __init__(self, colors_file: str = None, color_metric: str = "ciede2000",
                 palette_dir: str = None):
        self.colors_file = colors_file
        self.palette = None
        self.color_metric = color_metric
        # palette 目录（各品牌 JSON 所在），默认 src/assets/palette
        self.palette_dir = palette_dir or (
            os.path.join(os.path.dirname(colors_file), 'palette') if colors_file else None)
        self.brand = 'mard'          # 当前品牌 key
        self.brand_label = self.BRANDS['mard'][0]
        self._load_or_create_palette()

    def _load_or_create_palette(self):
        """Load palette from file or create default with fallback"""
        if self.colors_file:
            try:
                if os.path.exists(self.colors_file):
                    with open(self.colors_file, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                    self.palette = ColorPalette.from_dict(data)
                    self.palette.set_color_metric(self.color_metric)
                    count = len(self.palette.colors)
                    print(f"成功加载颜色表: {self.colors_file} ({count} 种颜色)")
                    if count < 50:
                        print(f"警告: 加载的颜色数量偏少 ({count})，可能使用了回退调色板")
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

    def load_palette(self, data: List[Dict], colors_file: str = None):
        """Swap in a different bead palette (other colors / numbering systems).

        This is the extension point for supporting bead brands or custom color
        sets beyond the bundled MARD 221 palette (e.g. Perler / Artkal / Hama,
        or any custom code+name+hex list). The rest of the pipeline (matching,
        quantize, BOM, chart render) works off ``self.palette`` generically, so
        replacing it here propagates everywhere with no further changes.

        Args:
            data: list of color dicts, each ``{"code","name","hex"}`` and
                optionally ``"lab"`` (measured CIE LAB for better matching).
                Codes may use any numbering scheme (A1.., H1.., P01.., ...).
            colors_file: optional path to persist this palette (sets
                ``self.colors_file`` so future loads/saves use it).
        """
        self.palette = ColorPalette.from_dict(data)
        self.palette.set_color_metric(self.color_metric)
        if colors_file is not None:
            self.colors_file = colors_file
        return len(self.palette.colors)

    def load_palette_file(self, filepath: str):
        """Load + swap in a palette from a JSON file (see :meth:`load_palette`)."""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        return self.load_palette(data, colors_file=filepath)

    def load_brand(self, key: str):
        """切换到指定品牌的颜色库。返回 (brand_label, 颜色数)。"""
        if key not in self.BRANDS:
            raise ValueError(f"未知品牌: {key}（支持: {', '.join(self.BRANDS)}）")
        label, fname = self.BRANDS[key]
        path = os.path.join(self.palette_dir, fname) if self.palette_dir else None
        if not path or not os.path.exists(path):
            raise ValueError(f"品牌颜色文件不存在: {path}")
        count = self.load_palette_file(path)
        self.brand = key
        self.brand_label = label
        return label, count

    def set_color_metric(self, metric: str):
        """Set the color distance metric"""
        if self.palette:
            self.palette.set_color_metric(metric)
        self.color_metric = metric

    def get_color_metric(self) -> str:
        """Get the current color distance metric"""
        return self.color_metric if self.palette else "ciede2000"

    def update_from_remote(self, colors_data: List[Dict]):
        """Update palette from remote data"""
        self.palette = ColorPalette.from_dict(colors_data)
        self.palette.set_color_metric(self.color_metric)
        if self.colors_file:
            self.palette.save_to_json(self.colors_file)

    def quantize_image(self, image_array: np.ndarray, color_limit: int = None,
                       salience_strength: float = 1.0, dither: bool = False,
                       metric: str = None, dither_strength: float = 1.0,
                       icm_smooth: float = 0.0) -> Tuple[np.ndarray, Dict]:
        """Quantize image to palette colors.

        With color_limit set, uses salience-weighted K-means in LAB space so that
        rare-but-important detail colors (long tail) are preserved instead of
        being dropped by naive top-N-by-count.

        Args:
            image_array: RGB image (uint8 or float)
            color_limit: max number of distinct colors (None/0 = unlimited)
            salience_strength: 0-2, weight given to rare/high-contrast colors
            dither: apply Floyd-Steinberg error diffusion in final assignment
            metric: distance metric override (defaults to palette metric)
        """
        if image_array.dtype != np.uint8:
            image_array = (image_array * 255).astype(np.uint8)
        metric = metric or self.palette.color_metric

        h, w = image_array.shape[:2]
        img = image_array if len(image_array.shape) == 3 else cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)
        pixels = img.reshape(-1, 3)

        palette_rgb = self.palette._palette_rgb

        unique_count = np.unique(pixels, axis=0).shape[0]

        n_palette = len(self.palette.colors)
        if (not color_limit or color_limit <= 0
                or int(color_limit) >= unique_count
                or int(color_limit) >= n_palette):
            # Unlimited, OR the requested limit meets/exceeds the number of
            # distinct colors actually present, OR it meets/exceeds the size of
            # the physical palette itself (can't use more bead colors than exist).
            # In these cases K-means would degenerate and, with forced de-dup,
            # invent spurious extra bead colors. Map every pixel to its nearest
            # bead color directly (uses all real colors, no extras).
            idx = self.palette.get_closest_indices_batch(pixels, metric)
            if icm_smooth and icm_smooth > 0:
                idx = self._icm_refine(img, idx, palette_rgb, icm_smooth, metric)
            if dither:
                output, dither_idx = self._floyd_steinberg(img, palette_rgb, metric, dither_strength)
                # BOM must reflect the dithered assignment actually rendered,
                # not the pre-dither nearest-color indices.
                usage = self._usage_from_indices(dither_idx)
            else:
                output = palette_rgb[idx]
                usage = self._usage_from_indices(idx)
            return output.reshape(h, w, 3).astype(np.uint8), usage

        # ---- Color-limited: salience-weighted palette K-center selection ----
        K = int(color_limit)
        Z = self.palette._rgb_batch_to_lab(pixels)          # (N,3) LAB float
        weights = self._salience_weights(img, salience_strength)  # (N,)

        # Select up to K physical bead colors directly from the palette,
        # preserving chroma so a vivid region keeps a vivid bead (no hue shift).
        center_idx = self._select_palette_colors(img, Z, weights, K, metric)
        K = len(center_idx)
        bead_rgb = palette_rgb[center_idx]                  # (K,3)
        centers = pal_lab = self.palette._palette_lab[center_idx]  # (K,3) LAB

        # Assign each pixel to its nearest selected bead (chroma-penalized), so
        # a vivid pixel is not captured by a grey bead merely on raw distance.
        if metric == "ciede2000":
            Dc = _ciede2000(Z, centers)                     # (N,K)
        else:
            Dc = ((Z[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        src_c = np.hypot(Z[:, 1], Z[:, 2])
        cen_c = np.hypot(centers[:, 1], centers[:, 2])[None, :]
        sat = src_c >= self._CHROMA_SAT_MIN
        pen = np.zeros_like(Dc)
        if sat.any():
            floor = (src_c[sat] - self._CHROMA_MATCH_TOL)[:, None]
            pen[sat] = np.maximum(0.0, floor - cen_c) * self._CHROMA_SOFT_PENALTY
        if (~sat).any():
            allow = (src_c[~sat] + self._CHROMA_ALLOW_BOOST)[:, None]
            pen[~sat] = np.maximum(0.0, cen_c - allow) * self._CHROMA_SOFT_PENALTY
        labels = (Dc + pen).argmin(axis=1)                  # (N,) which bead
        mapped_idx = center_idx[labels]                     # (N,) palette index

        # ICM spatial-coherence refinement operates on the per-pixel palette
        # assignment to merge fragmented regions and remove isolated speckles.
        if icm_smooth and icm_smooth > 0:
            sal = self._salience_map(img)                   # (h,w) 0-1
            mapped_idx = self._icm_refine(img, mapped_idx, palette_rgb,
                                          icm_smooth, metric, salience=sal)
            # Re-derive centroid labels for the optional constrained dither.
            labels = self._assign_labels(Z, self.palette._palette_lab[mapped_idx])

        if dither:
            output, dither_labels = self._floyd_steinberg_to_set(img, bead_rgb, labels, Z, metric, dither_strength)
            # Map the dithered per-pixel bead-set labels back to palette indices
            # so the BOM matches what is actually drawn.
            usage = self._usage_from_indices(center_idx[dither_labels])
        else:
            output = palette_rgb[mapped_idx]
            usage = self._usage_from_indices(mapped_idx)
        return output.reshape(h, w, 3).astype(np.uint8), usage

    # ---- helpers ---------------------------------------------------------

    # Chroma-preservation tuning for palette selection. Real bead colors that a
    # painter perceives as "the same hue" rarely differ by more than ~12 chroma
    # units from the source; letting a vivid source collapse to a much greyer
    # bead (or a pastel source jump to a vivid bead) is exactly the hue-shift
    # failure seen in the wild (yellow->orange, blue->purple, pink->gray).
    _CHROMA_SAT_MIN = 30.0        # below this a source counts as unsaturated
    _CHROMA_MATCH_TOL = 12.0      # saturated source: keep candidate chroma >= src - tol
    _CHROMA_ALLOW_BOOST = 15.0    # unsaturated source: allow up to src + boost
    _CHROMA_SOFT_PENALTY = 0.6    # per-chroma-unit dE penalty beyond allowance
    _CHROMA_RELAX = 1.12          # multiplicative slack before accepting a worse pick

    def _chroma_aware_pick(self, lab: np.ndarray, d: np.ndarray) -> int:
        """Pick a palette index for a single LAB color with chroma preservation.

        `d` is the (P,) delta-E (or LAB-sq) distance from the source to every
        palette color. A pure argmin can pick a lower-chroma bead when its dE is
        marginally smaller, which reads as a hue shift. For a saturated source we
        re-rank: prefer candidates whose chroma stays within tolerance of the
        source, only accepting a lower-chroma pick if it is clearly closer.
        Returns a palette index.
        """
        d = np.asarray(d, dtype=np.float64)
        best = int(np.argmin(d))
        pal_lab = self.palette._palette_lab
        src_c = float(np.hypot(lab[1], lab[2]))
        pal_c = np.hypot(pal_lab[:, 1], pal_lab[:, 2])

        if src_c < self._CHROMA_SAT_MIN:
            # Unsaturated source: discourage jumping to a much MORE saturated
            # bead (pastel pink -> vivid pink) unless clearly closer.
            allowed = src_c + self._CHROMA_ALLOW_BOOST
            pen = np.maximum(0.0, pal_c - allowed) * self._CHROMA_SOFT_PENALTY
            return int(np.argmin(d + pen))

        # Saturated source: prefer candidates that keep the chroma up.
        floor = src_c - self._CHROMA_MATCH_TOL
        keep = pal_c >= floor
        if keep.any():
            kidx = int(np.flatnonzero(keep)[np.argmin(d[keep])])
            # Only fall back to a lower-chroma bead if it is decisively closer.
            if d[best] <= d[kidx] * (self._CHROMA_RELAX - 0.12):  # ~equal
                return best
            return kidx
        return best

    def _top_palette_colors(self, lab: np.ndarray, K: int, metric: str,
                            extra: int = 8) -> List[int]:
        """Shortlist of promising palette indices for a single LAB color.

        Combines raw delta-E proximity with chroma preservation so the candidate
        pool for K-center selection already contains the "right hue" beads rather
        than only the closest-by-dE (which skew low-chroma).
        """
        pal_lab = self.palette._palette_lab
        if metric == "ciede2000":
            d = _ciede2000(np.atleast_2d(lab), pal_lab)[0]
        else:
            d = ((pal_lab - lab) ** 2).sum(-1)
        pick = self._chroma_aware_pick(lab, d)
        order = np.argsort(d)[: max(extra, K)]
        cand = [pick] + [int(i) for i in order]
        # de-dup preserve order
        seen, out = set(), []
        for i in cand:
            if i not in seen:
                seen.add(i)
                out.append(int(i))
        return out

    def _chroma_penalty(self, lab: np.ndarray) -> np.ndarray:
        """(P,) additive penalty discouraging chroma mismatch for a source color.

        Used to re-weight the palette histogram selection so a grey bead is not
        chosen to represent a vivid region (and vice versa).
        """
        pal_lab = self.palette._palette_lab
        src_c = float(np.hypot(lab[1], lab[2]))
        pal_c = np.hypot(pal_lab[:, 1], pal_lab[:, 2])
        if src_c < self._CHROMA_SAT_MIN:
            excess = np.maximum(0.0, pal_c - (src_c + self._CHROMA_ALLOW_BOOST))
        else:
            excess = np.maximum(0.0, (src_c - self._CHROMA_MATCH_TOL) - pal_c)
        return excess * self._CHROMA_SOFT_PENALTY

    def _select_palette_colors(self, img: np.ndarray, Z: np.ndarray,
                               weights: np.ndarray, K: int, metric: str) -> np.ndarray:
        """Choose up to K physical palette bead colors directly (no LAB-centroid
        averaging). This replaces the "K-means centroid -> map to bead" step whose
        averaging produced shifted, lower-chroma source colors and thus wrong-hue
        beads.

        Approach: build a salience-weighted histogram of per-pixel nearest
        palette colors (chroma-aware), seed with the dominant color, then greedily
        add the candidate that maximizes (weighted error if used) — a farthest-
        point style K-centers over palette candidates. Returns (K,) palette idx.
        """
        pal_lab = self.palette._palette_lab
        P = len(self.palette.colors)
        K = max(1, min(int(K), P))

        # Per-pixel nearest bead (chroma-aware) + histogram of weights.
        if metric == "ciede2000":
            dpix = _ciede2000(Z, pal_lab)                       # (N,P)
        else:
            dpix = ((Z[:, None, :] - pal_lab[None, :, :]) ** 2).sum(-1)
        nearest = dpix.argmin(axis=1)
        hist = np.bincount(nearest, weights=weights, minlength=P).astype(np.float64)

        # Candidate pool: top colors by weighted support + chroma-aware picks
        # for the heaviest bins (ensures the right-hue variant is present).
        order = np.argsort(-hist)
        support = order[: max(K * 3, K + 6)]
        cand = list(dict.fromkeys([int(i) for i in support if hist[i] > 0]))

        if not cand:
            cand = [int(order[0])]

        # Distance from every pixel to each candidate, chroma-penalized so a
        # vivid region is not "served" by a grey bead and counted as satisfied.
        def penalized_d(cidx):
            sub = dpix[:, cidx]                                  # (N,C)
            # penalty per candidate chroma vs pixel chroma
            src_c = np.hypot(Z[:, 1], Z[:, 2])                   # (N,)
            pen_c = np.hypot(pal_lab[cidx, 1], pal_lab[cidx, 2]) # (C,)
            sat = src_c >= self._CHROMA_SAT_MIN
            pen = np.zeros((len(Z), len(cidx)), dtype=np.float64)
            # vivid pixels want vivid candidates
            if sat.any():
                floor = (src_c[sat] - self._CHROMA_MATCH_TOL)[:, None]
                pen[sat] = np.maximum(0.0, floor - pen_c[None, :]) * self._CHROMA_SOFT_PENALTY
            # dull pixels want dull candidates
            if (~sat).any():
                allow = (src_c[~sat] + self._CHROMA_ALLOW_BOOST)[:, None]
                pen[~sat] = np.maximum(0.0, pen_c[None, :] - allow) * self._CHROMA_SOFT_PENALTY
            return sub + pen

        D = penalized_d(cand)                                    # (N,C) penalized
        # current best (penalized) distance to the chosen set
        chosen = [int(np.argmax(hist))]
        if chosen[0] not in cand:
            chosen = [cand[0]]
        cpos = {c: i for i, c in enumerate(cand)}
        best_d = D[:, cpos[chosen[0]]].copy()

        while len(chosen) < K and len(chosen) < len(cand):
            # improvement each candidate would bring = sum w * max(0, best_d - d_c)
            gain = np.zeros(len(cand), dtype=np.float64)
            for ci in range(len(cand)):
                if cand[ci] in chosen:
                    gain[ci] = -np.inf
                    continue
                imp = np.maximum(0.0, best_d - D[:, ci])
                gain[ci] = float((weights * imp).sum())
            nxt = int(np.argmax(gain))
            if not np.isfinite(gain[nxt]):
                break
            chosen.append(cand[nxt])
            best_d = np.minimum(best_d, D[:, nxt])

        return np.array(chosen, dtype=np.int64)

    def _usage_from_indices(self, idx: np.ndarray) -> Dict:
        codes = [self.palette.colors[i].code for i in idx]
        usage = {}
        for c in codes:
            usage[c] = usage.get(c, 0) + 1
        return usage

    def _salience_map(self, img: np.ndarray) -> np.ndarray:
        """Per-pixel salience in [0,1] (saturation x local contrast), shape (h,w).

        Used to relax the ICM smoothness prior on important detail regions
        (eyes, outlines) so they are not over-smoothed away.
        """
        h, w = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.float64) / 255.0
        sat = hsv[:, :, 1]
        lab_img = self.palette._rgb_batch_to_lab(img.reshape(-1, 3)).reshape(h, w, 3)
        blur = cv2.GaussianBlur(lab_img, (3, 3), 0)
        contrast = np.linalg.norm(lab_img - blur, axis=2)
        contrast = contrast / (contrast.max() + 1e-6)
        sal = np.clip(0.5 * sat + 0.5 * contrast, 0.0, 1.0)
        # Local (connected) salience: blur so an ISOLATED speckle's high
        # saturation/contrast is pulled down by its bland neighbors, while a
        # coherent detailed region (eye, outline) keeps its protection. This is
        # what lets ICM remove single-pixel noise yet preserve real detail.
        sal = cv2.GaussianBlur(sal, (5, 5), 0)
        return sal

    def _icm_refine(self, img: np.ndarray, idx: np.ndarray, palette_rgb: np.ndarray,
                    strength: float, metric: str, salience: np.ndarray = None,
                    iters: int = 3) -> np.ndarray:
        """ICM spatial-coherence refinement (Huang et al. TIP2015-style).

        Each pixel currently assigned a palette color may be re-assigned to a
        nearby candidate color if that lowers a combined energy:
            E = color_error(new) + strength * isolation_penalty(new)
        where isolation_penalty counts same-color neighbors (a pixel surrounded
        by color X pays little to also become X; an isolated speckle pays a lot
        to stay different). Salient pixels get a reduced smoothness weight so
        genuine details survive.

        Args:
            img: (h,w,3) uint8 RGB
            idx: (N,) palette index per pixel (current assignment)
            palette_rgb: (P,3) uint8 palette RGB
            strength: smoothness weight (typical 0.3-1.0)
            metric: distance metric for the color-error term
            salience: optional (h,w) 0-1 map; high salience => less smoothing
            iters: ICM passes over the image
        Returns:
            (N,) refined palette index per pixel
        """
        h, w = img.shape[:2]
        L = idx.reshape(h, w).astype(np.int64).copy()
        pal_lab = self.palette._palette_lab                      # (P,3)
        pix_lab = self.palette._rgb_batch_to_lab(img.reshape(-1, 3)).reshape(h, w, 3)
        if salience is None:
            salience = self._salience_map(img)
        # Per-pixel smoothness weight; salient detail gets less smoothing.
        lam = float(strength) * (1.0 - 0.7 * salience)           # (h,w)
        # Scale lambda into LAB-distance units so the neighbor-agreement reward
        # can actually compete with the color error (an isolated speckle should
        # be winnable by its neighbors). ~25 LAB units ~ a clearly visible shift.
        lam = lam * 25.0

        for _ in range(iters):
            changed = 0
            for y in range(h):
                for x in range(w):
                    # Candidate colors = current + the (distinct) neighbor colors.
                    cand = [int(L[y, x])]
                    for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                        if 0 <= ny < h and 0 <= nx < w:
                            c = int(L[ny, nx])
                            if c not in cand:
                                cand.append(c)
                    if len(cand) == 1:
                        continue  # uniform neighborhood, nothing to decide
                    pl = pix_lab[y, x]
                    cc = pal_lab[cand]                              # (C,3)
                    if metric == "ciede2000":
                        ce = _ciede2000(np.atleast_2d(pl), cc)[0]
                    else:
                        ce = ((cc - pl) ** 2).sum(-1)
                    # neighbor-agreement reward per candidate
                    match = np.zeros(len(cand), dtype=np.float64)
                    for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                        if 0 <= ny < h and 0 <= nx < w:
                            nl = int(L[ny, nx])
                            if nl in cand:
                                match[cand.index(nl)] += 1.0
                    energy = ce - lam[y, x] * match
                    best_local = int(energy.argmin())
                    best = cand[best_local]
                    if best != int(L[y, x]):
                        L[y, x] = best
                        changed += 1
            if changed == 0:
                break
        return L.reshape(-1)

    def _salience_weights(self, img: np.ndarray, strength: float) -> np.ndarray:
        """Compute per-pixel salience weight = saturation x contrast x rarity."""
        h, w = img.shape[:2]
        # saturation
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).reshape(-1, 3)
        sat = hsv[:, 1].astype(np.float64) / 255.0
        # local contrast (LAB distance to 3x3 blur)
        lab_img = self.palette._rgb_batch_to_lab(img.reshape(-1, 3)).reshape(h, w, 3)
        blur = cv2.GaussianBlur(lab_img, (3, 3), 0)
        contrast = np.linalg.norm(lab_img - blur, axis=2).reshape(-1)
        contrast = contrast / (contrast.max() + 1e-6)
        # rarity: inverse of coarse color-bin frequency
        pix = img.reshape(-1, 3).astype(np.int32)
        bins = (pix[:, 0] // 32) * 64 + (pix[:, 1] // 32) * 8 + (pix[:, 2] // 32)
        counts = np.bincount(bins, minlength=512).astype(np.float64)
        rarity = 1.0 / (counts[bins] + 1e-6)
        rarity = rarity / rarity.max()

        # Salience weight: strength must genuinely separate rare-but-important
        # detail colors from common ones. Use a contrast curve so the slider
        # (0-2) visibly changes which colors survive clustering.
        # - rarity pushed through sqrt() spreads the near-zero tail so the
        #   strength term has something to act on for semi-rare colors too.
        # - exponential (base + rarity)^strength makes strength amplify rare
        #   colors strongly while leaving common colors near 1x.
        r = np.sqrt(np.clip(rarity, 0.0, 1.0))
        sat_term = 0.4 + 0.6 * sat
        contrast_term = 0.5 + 0.5 * contrast
        rarity_term = np.power(1.0 + 3.0 * r, strength)
        weights = sat_term * contrast_term * rarity_term
        weights = weights / (weights.mean() + 1e-9)
        return weights

    @staticmethod
    def _weighted_kmeans(Z: np.ndarray, w: np.ndarray, K: int, iters: int = 20, seed: int = 42) -> np.ndarray:
        rng = np.random.default_rng(seed)
        p = w / w.sum()
        centers = [Z[rng.choice(len(Z), p=p)]]
        for _ in range(K - 1):
            d = np.min(((Z[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
            pp = w * d
            s = pp.sum()
            if s <= 0:
                pp = w
                s = pp.sum()
            centers.append(Z[rng.choice(len(Z), p=pp / s)])
        C = np.array(centers, dtype=np.float64)
        for _ in range(iters):
            dist = ((Z[:, None, :] - C[None]) ** 2).sum(-1)
            labels = dist.argmin(1)
            min_d = dist[np.arange(len(Z)), labels]
            for k in range(K):
                mask = labels == k
                if mask.any():
                    wk = w[mask][:, None]
                    C[k] = (Z[mask] * wk).sum(0) / (wk.sum() + 1e-9)
                else:
                    # Empty cluster: reseed at the worst-served pixel so the
                    # center is not frozen as a stale "orphan" centroid.
                    C[k] = Z[int(np.argmax(min_d))]
        return C

    @staticmethod
    def _assign_labels(Z: np.ndarray, centers: np.ndarray) -> np.ndarray:
        dist = ((Z[:, None, :] - centers[None]) ** 2).sum(-1)
        return dist.argmin(1)

    def _lab_batch_to_rgb(self, lab: np.ndarray) -> np.ndarray:
        """standardized LAB (K,3) -> uint8 RGB"""
        arr = lab.astype(np.float64).copy()
        arr[:, 0] = arr[:, 0] * 255.0 / 100.0
        arr[:, 1] = arr[:, 1] + 128.0
        arr[:, 2] = arr[:, 2] + 128.0
        arr = np.clip(arr, 0, 255).astype(np.uint8).reshape(-1, 1, 3)
        rgb = cv2.cvtColor(arr, cv2.COLOR_Lab2RGB).reshape(-1, 3)
        return rgb

    def _dedupe_indices(self, idx: np.ndarray, centers_rgb: np.ndarray, metric: str, K: int) -> np.ndarray:
        """Replace duplicate palette mappings with next-nearest distinct colors."""
        idx = idx.copy()
        seen = set()
        for i, ind in enumerate(idx):
            if ind in seen:
                # find next nearest distinct palette color for this centroid,
                # using the SAME metric as the main mapping for consistency.
                lab = self.palette._rgb_batch_to_lab(centers_rgb[i][None, :])
                if metric == "ciede2000":
                    d = _ciede2000(lab, self.palette._palette_lab)[0]
                else:
                    d = ((lab[:, None, :] - self.palette._palette_lab[None, :, :]) ** 2).sum(-1)[0]
                order = np.argsort(d)
                for cand in order:
                    if cand not in seen:
                        idx[i] = cand
                        break
            seen.add(idx[i])
        return idx

    def _floyd_steinberg(self, img: np.ndarray, palette_rgb: np.ndarray,
                         metric: str, strength: float = 1.0) -> np.ndarray:
        """Error diffusion toward the full palette, computed in LAB space.

        Working in LAB (rather than RGB) makes the diffused error perceptually
        meaningful, avoiding the hue shifts RGB diffusion causes in dark and
        highly-saturated regions. `strength` (0-1) scales how much error is
        propagated, so partial diffusion softens banding without speckle.

        Returns (quantized image uint8 RGB, out): the dithered image and the
        per-pixel palette indices (N,) that were actually assigned, so callers
        can build a BOM consistent with the rendered image.
        """
        h, w = img.shape[:2]
        s = float(np.clip(strength, 0.0, 1.0))
        # Pixel -> LAB working buffer; palette LAB is precomputed.
        work = self.palette._rgb_batch_to_lab(img.reshape(-1, 3)).reshape(h, w, 3)
        pal_lab = self.palette._palette_lab
        out = np.zeros((h * w,), dtype=np.int64)
        for y in range(h):
            for x in range(w):
                old = work[y, x]
                if metric == "ciede2000":
                    d = _ciede2000(old[None, :], pal_lab)[0]
                else:
                    d = ((pal_lab - old) ** 2).sum(-1)
                k = int(d.argmin())
                out[y * w + x] = k
                err = (old - pal_lab[k]) * s
                if x + 1 < w:
                    work[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x > 0:
                        work[y + 1, x - 1] += err * 3 / 16
                    work[y + 1, x] += err * 5 / 16
                    if x + 1 < w:
                        work[y + 1, x + 1] += err * 1 / 16
        return palette_rgb[out].reshape(h, w, 3).astype(np.uint8), out

    def _floyd_steinberg_to_set(self, img: np.ndarray, bead_rgb: np.ndarray,
                                labels: np.ndarray, Z: np.ndarray, metric: str,
                                strength: float = 1.0) -> np.ndarray:
        """Error diffusion constrained to the selected bead color set (LAB matching).

        Returns (quantized image uint8 RGB, out): the dithered image and the
        per-pixel bead-set labels (N,) actually assigned, so callers can map them
        back to palette indices for a BOM consistent with the rendered image.
        """
        h, w = img.shape[:2]
        s = float(np.clip(strength, 0.0, 1.0))
        bead_lab = self.palette._rgb_batch_to_lab(bead_rgb)
        work_lab = Z.reshape(h, w, 3).astype(np.float64).copy()
        out = np.zeros((h * w,), dtype=np.int64)
        for y in range(h):
            for x in range(w):
                old = work_lab[y, x]
                d = ((bead_lab - old) ** 2).sum(-1)
                k = int(d.argmin())
                out[y * w + x] = k
                new = bead_lab[k]
                err = (old - new) * s
                if x + 1 < w:
                    work_lab[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x > 0:
                        work_lab[y + 1, x - 1] += err * 3 / 16
                    work_lab[y + 1, x] += err * 5 / 16
                    if x + 1 < w:
                        work_lab[y + 1, x + 1] += err * 1 / 16
        return bead_rgb[out].reshape(h, w, 3).astype(np.uint8), out


if __name__ == '__main__':
    manager = ColorManager()
    palette = manager.get_palette()
    print(f"调色板包含 {len(palette.colors)} 种颜色")
    for color in palette.colors[:5]:
        print(f"{color.code}: {color.name} {color.hex}")
