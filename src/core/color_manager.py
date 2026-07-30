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

    def __init__(self, colors_file: str = None, color_metric: str = "ciede2000"):
        self.colors_file = colors_file
        self.palette = None
        self.color_metric = color_metric
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
                       metric: str = None, dither_strength: float = 1.0) -> Tuple[np.ndarray, Dict]:
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

        if not color_limit or color_limit <= 0 or int(color_limit) >= unique_count:
            # Unlimited, OR the requested limit meets/exceeds the number of
            # distinct colors actually present. In the latter case K-means would
            # degenerate to one-cluster-per-color and, with forced de-dup, invent
            # spurious extra bead colors. Just map every pixel to its nearest
            # bead color directly (uses all real colors, no extras).
            idx = self.palette.get_closest_indices_batch(pixels, metric)
            output = palette_rgb[idx]
            if dither:
                output = self._floyd_steinberg(img, palette_rgb, metric, dither_strength)
            usage = self._usage_from_indices(idx)
            return output.reshape(h, w, 3).astype(np.uint8), usage

        # ---- Color-limited: salience-weighted K-means ----
        K = int(color_limit)
        Z = self.palette._rgb_batch_to_lab(pixels)          # (N,3) LAB float
        weights = self._salience_weights(img, salience_strength)  # (N,)

        K = max(1, K)

        centers = self._weighted_kmeans(Z, weights, K, iters=20, seed=42)  # (K,3) LAB

        # Map each LAB centroid back to a real palette bead color
        centers_rgb = self._lab_batch_to_rgb(centers)       # (K,3) uint8
        center_idx = self.palette.get_closest_indices_batch(centers_rgb, metric)
        # De-duplicate: ensure at most K distinct colors
        center_idx = self._dedupe_indices(center_idx, centers_rgb, metric, K)
        bead_rgb = palette_rgb[center_idx]                  # (K,3)

        # Assign each pixel to nearest centroid, then to that centroid's bead color
        labels = self._assign_labels(Z, centers)            # (N,)
        mapped_idx = center_idx[labels]                     # (N,) palette index per pixel
        output = palette_rgb[mapped_idx]

        if dither:
            output = self._floyd_steinberg_to_set(img, bead_rgb, labels, Z, metric, dither_strength)

        usage = self._usage_from_indices(mapped_idx)
        return output.reshape(h, w, 3).astype(np.uint8), usage

    # ---- helpers ---------------------------------------------------------

    def _usage_from_indices(self, idx: np.ndarray) -> Dict:
        codes = [self.palette.colors[i].code for i in idx]
        usage = {}
        for c in codes:
            usage[c] = usage.get(c, 0) + 1
        return usage

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

        weights = (0.4 + 0.6 * sat) * (0.5 + 0.5 * contrast) * (0.5 + strength * rarity)
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

        Returns the quantized image in palette colors (uint8 RGB).
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
        return palette_rgb[out].reshape(h, w, 3).astype(np.uint8)

    def _floyd_steinberg_to_set(self, img: np.ndarray, bead_rgb: np.ndarray,
                                labels: np.ndarray, Z: np.ndarray, metric: str,
                                strength: float = 1.0) -> np.ndarray:
        """Error diffusion constrained to the selected bead color set (LAB matching)."""
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
        return bead_rgb[out].reshape(h, w, 3).astype(np.uint8)


if __name__ == '__main__':
    manager = ColorManager()
    palette = manager.get_palette()
    print(f"调色板包含 {len(palette.colors)} 种颜色")
    for color in palette.colors[:5]:
        print(f"{color.code}: {color.name} {color.hex}")
