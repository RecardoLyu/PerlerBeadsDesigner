"""
Image segmentation module for foreground/background separation
"""
import cv2
import numpy as np
from typing import Tuple, List
import os


class ImageSegmentation:
    """Handles image segmentation and foreground detection"""
    
    def __init__(self):
        self.mask = None
        self.marked_image = None
    
    def grabcut_interactive(self, image: np.ndarray, 
                           points: List[Tuple[int, int]], 
                           is_foreground: bool = True) -> np.ndarray:
        """
        Interactive GrabCut segmentation with point hints
        
        Args:
            image: Input image (RGB)
            points: List of (x, y) points marked by user
            is_foreground: True for foreground points, False for background
        
        Returns:
            Binary mask
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("请提供有效的RGB图像")
        
        # Convert to BGR for OpenCV
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Initialize mask
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        
        # Mark foreground and background points
        if is_foreground:
            for x, y in points:
                cv2.circle(mask, (x, y), 5, cv2.GC_FGD, -1)
        else:
            for x, y in points:
                cv2.circle(mask, (x, y), 5, cv2.GC_BGD, -1)
        
        # Run GrabCut
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)
        
        cv2.grabCut(image_bgr, mask, None, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_MASK)
        
        # Create output mask
        output_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8') * 255
        self.mask = output_mask
        
        return output_mask
    
    def grabcut_rect(self, image: np.ndarray, 
                     x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """
        GrabCut segmentation with rectangular ROI
        
        Args:
            image: Input image (RGB)
            x1, y1: Top-left corner of ROI
            x2, y2: Bottom-right corner of ROI
        
        Returns:
            Binary mask
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("请提供有效的RGB图像")
        
        # Convert to BGR
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Create rectangle
        rect = (x1, y1, x2 - x1, y2 - y1)
        
        # Initialize mask
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        
        # Run GrabCut
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)
        
        cv2.grabCut(image_bgr, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
        
        # Create output mask
        output_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8') * 255
        self.mask = output_mask
        
        return output_mask
    
    def watershed_segmentation(self, image: np.ndarray, 
                               foreground_points: List[Tuple[int, int]],
                               background_points: List[Tuple[int, int]]) -> np.ndarray:
        """
        Watershed algorithm for segmentation
        
        Args:
            image: Input image (RGB)
            foreground_points: Points in foreground regions
            background_points: Points in background regions
        
        Returns:
            Binary mask
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("请提供有效的RGB图像")
        
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Create marker image
        h, w = image.shape[:2]
        markers = np.zeros((h, w), dtype=np.int32)
        
        # Mark foreground
        for x, y in foreground_points:
            cv2.circle(markers, (x, y), 10, 1, -1)
        
        # Mark background
        for x, y in background_points:
            cv2.circle(markers, (x, y), 10, 2, -1)
        
        # Run watershed
        cv2.watershed(image_bgr, markers)
        
        # Create mask from markers
        mask = np.where(markers == 1, 255, 0).astype(np.uint8)
        self.mask = mask
        
        return mask
    
    def watershed_auto(self, image: np.ndarray) -> np.ndarray:
        """
        Marker-based watershed with automatic seeds (no user input).

        Pipeline: grayscale -> Otsu -> opening denoise -> distance transform
        for sure-foreground seeds -> dilation for sure-background -> markers ->
        cv2.watershed. The foreground orientation (dark vs. bright subject) is
        auto-picked so the central image region ends up foreground.

        Args:
            image: Input image (RGB)

        Returns:
            Binary mask (0/255), foreground = 255
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("请提供有效的RGB图像")

        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # Auto-orient: binarize so the central region becomes foreground (white).
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, bw_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        h, w = gray.shape
        cy1, cy2, cx1, cx2 = h // 4, 3 * h // 4, w // 4, 3 * w // 4
        center = (slice(cy1, cy2), slice(cx1, cx2))
        fg = bw if bw[center].mean() >= bw_inv[center].mean() else bw_inv

        # Denoise and derive sure foreground / sure background.
        kernel = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=2)
        sure_bg = cv2.dilate(opening, kernel, iterations=3)
        dist = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
        max_dist = dist.max() if dist.max() > 0 else 1.0
        _, sure_fg = cv2.threshold(dist, 0.4 * max_dist, 255, cv2.THRESH_BINARY)
        sure_fg = sure_fg.astype(np.uint8)
        unknown = cv2.subtract(sure_bg, sure_fg)

        # Build markers: background = 1, foreground components >= 2.
        num, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0

        cv2.watershed(image_bgr, markers)

        # Foreground = all marker labels >= 2.
        mask = np.where(markers >= 2, 255, 0).astype(np.uint8)
        self.mask = mask
        return mask

    def otsu_segment(self, image: np.ndarray) -> np.ndarray:
        """
        Otsu automatic thresholding, auto-oriented so the central subject is
        foreground. Very fast; best for high subject/background contrast.

        Args:
            image: Input image (RGB)

        Returns:
            Binary mask (0/255), foreground = 255
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("请提供有效的RGB图像")

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, bw_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        h, w = gray.shape
        center = (slice(h // 4, 3 * h // 4), slice(w // 4, 3 * w // 4))
        mask = bw if bw[center].mean() >= bw_inv[center].mean() else bw_inv

        # Light closing to fill pinholes.
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        self.mask = mask
        return mask

    def slic_segment(self, image: np.ndarray, n_segments: int = 150) -> np.ndarray:
        """
        SLIC superpixel segmentation aggregated into a foreground mask.

        Over-segments with SLIC (Lab space), then labels each superpixel
        foreground/background via Otsu on the per-superpixel mean brightness,
        auto-oriented so the central region is foreground. Good for flat-color
        perler-bead source images with tidy edges.

        Args:
            image: Input image (RGB)
            n_segments: Approximate number of superpixels

        Returns:
            Binary mask (0/255), foreground = 255
        """
        if image is None or len(image.shape) != 3:
            raise ValueError("请提供有效的RGB图像")

        from skimage.segmentation import slic

        segments = slic(image, n_segments=n_segments, compactness=10,
                        start_label=0, channel_axis=-1)

        # Score each superpixel by how "subject-like" it is. Perler-bead
        # subjects are usually colorful; plain backgrounds are flat/gray, so
        # saturation separates them well. Fall back to brightness when the
        # image is near-grayscale (saturation carries no signal).
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        sat = hsv[:, :, 1].astype(np.float32)
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)

        flat_seg = segments.ravel()
        counts = np.bincount(flat_seg)
        counts[counts == 0] = 1

        def per_superpixel(feat):
            return np.bincount(flat_seg, weights=feat.ravel()) / counts

        sat_m = per_superpixel(sat)
        gray_m = per_superpixel(gray)
        feature = sat_m if sat_m.max() - sat_m.min() > 25 else gray_m

        # Split superpixels into foreground/background. Otsu degenerates when
        # the split is very lopsided (tiny within-class variance -> threshold
        # at the min -> everything foreground). Detect that and use a midpoint
        # split between the two clusters instead.
        feat_u8 = np.clip(feature, 0, 255).astype(np.uint8)
        thresh, _ = cv2.threshold(feat_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        frac = float((feature >= thresh).mean())
        if frac < 0.02 or frac > 0.98:
            thresh = (float(feature.min()) + float(feature.max())) / 2.0
        high_fg = feature >= thresh  # candidate: high-feature superpixels = subject

        # Auto-orient: compare the total feature mass captured in the central
        # region between the two orientations; pick the one that concentrates
        # the subject in the center. (Majority-of-labels fails when the subject
        # is over-segmented into many small superpixels.)
        h, w = gray.shape
        center_mask = np.zeros((h, w), dtype=bool)
        center_mask[h // 4:3 * h // 4, w // 4:3 * w // 4] = True
        feat_img = feature[segments]
        total = float(feat_img.sum())
        central_mass = float(feat_img[center_mask].sum()) / total if total > 0 else 0.0
        fg_labels = high_fg if central_mass >= 0.5 else ~high_fg

        mask = (fg_labels[segments]).astype(np.uint8) * 255
        self.mask = mask
        return mask

    def simple_threshold(self, image: np.ndarray, 
                        threshold_value: int = 127, 
                        use_otsu: bool = False) -> np.ndarray:
        """
        Simple thresholding for binary segmentation
        
        Args:
            image: Input image (RGB or grayscale)
            threshold_value: Threshold value (ignored if use_otsu=True)
            use_otsu: Use Otsu's method for automatic threshold
        
        Returns:
            Binary mask
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        if use_otsu:
            _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, mask = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
        
        self.mask = mask
        return mask
    
    def adaptive_threshold(self, image: np.ndarray, 
                          block_size: int = 11, 
                          constant: float = 2) -> np.ndarray:
        """
        Adaptive thresholding (good for varying illumination)
        
        Args:
            image: Input image (RGB or grayscale)
            block_size: Size of neighborhood area
            constant: Constant subtracted from mean
        
        Returns:
            Binary mask
        """
        # Ensure block_size is odd
        if block_size % 2 == 0:
            block_size += 1
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, block_size, constant)
        
        self.mask = mask
        return mask
    
    def color_range_threshold(self, image: np.ndarray, 
                             lower_rgb: Tuple[int, int, int],
                             upper_rgb: Tuple[int, int, int]) -> np.ndarray:
        """
        Threshold based on color range
        
        Args:
            image: Input image (RGB)
            lower_rgb: Lower bound of color range
            upper_rgb: Upper bound of color range
        
        Returns:
            Binary mask
        """
        # Convert RGB to HSV for better color range detection
        image_hsv = cv2.cvtColor(image if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB), 
                                 cv2.COLOR_RGB2HSV)
        
        # For simplicity, convert RGB bounds to BGR for cv2.inRange
        lower_bgr = (lower_rgb[2], lower_rgb[1], lower_rgb[0])
        upper_bgr = (upper_rgb[2], upper_rgb[1], upper_rgb[0])
        
        # This is a simplified approach; HSV might be more robust
        image_bgr = cv2.cvtColor(image if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB),
                                 cv2.COLOR_RGB2BGR)
        
        mask = cv2.inRange(image_bgr, lower_bgr, upper_bgr)
        self.mask = mask
        return mask
    
    @staticmethod
    def get_kernel(shape: str, kernel_size: int) -> np.ndarray:
        """
        Build a structuring element of the given shape.

        Args:
            shape: One of 'ellipse','rect','cross','vline','hline',
                   'diag1' (backslash), 'diag2' (slash), 'diamond'
            kernel_size: Size of the kernel (px)

        Returns:
            uint8 structuring element
        """
        k = max(1, int(kernel_size))
        # Force odd size so custom elements (np.eye / ones / diamond) are
        # symmetric about the anchor. An even-sized eye/line/diamond kernel has
        # a half-pixel anchor offset, which makes dilation grow one-sided and
        # produce spurious foreground along edges.
        if k % 2 == 0:
            k += 1
        if shape == 'rect':
            return cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        if shape == 'cross':
            return cv2.getStructuringElement(cv2.MORPH_CROSS, (k, k))
        if shape == 'vline':
            return np.ones((k, 1), dtype=np.uint8)
        if shape == 'hline':
            return np.ones((1, k), dtype=np.uint8)
        if shape == 'diag1':  # backslash \
            return np.eye(k, dtype=np.uint8)
        if shape == 'diag2':  # slash /
            return np.fliplr(np.eye(k, dtype=np.uint8))
        if shape == 'diamond':
            r = k // 2
            y, x = np.ogrid[-r:k - r, -r:k - r]
            return ((np.abs(x) + np.abs(y)) <= r).astype(np.uint8)
        # default: ellipse (disk)
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    def morph_close(self, mask: np.ndarray, kernel_size: int = 5, shape: str = 'ellipse') -> np.ndarray:
        """
        Morphological closing to fill holes

        Args:
            mask: Binary mask
            kernel_size: Size of morphological kernel
            shape: Structuring element shape (see get_kernel)

        Returns:
            Processed mask
        """
        kernel = self.get_kernel(shape, kernel_size)
        result = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        self.mask = result
        return result

    def morph_open(self, mask: np.ndarray, kernel_size: int = 5, shape: str = 'ellipse') -> np.ndarray:
        """
        Morphological opening to remove noise

        Args:
            mask: Binary mask
            kernel_size: Size of morphological kernel
            shape: Structuring element shape (see get_kernel)

        Returns:
            Processed mask
        """
        kernel = self.get_kernel(shape, kernel_size)
        result = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        self.mask = result
        return result

    def morph_erode(self, mask: np.ndarray, kernel_size: int = 5, shape: str = 'ellipse') -> np.ndarray:
        """
        Erosion: shrink foreground, remove thin connections/spurs

        Args:
            mask: Binary mask
            kernel_size: Size of morphological kernel
            shape: Structuring element shape (see get_kernel)

        Returns:
            Processed mask
        """
        kernel = self.get_kernel(shape, kernel_size)
        # borderValue=0: treat out-of-image as background so edge foreground
        # cannot pull phantom foreground from the boundary constant.
        result = cv2.erode(mask, kernel, iterations=1,
                           borderType=cv2.BORDER_CONSTANT, borderValue=0)
        self.mask = result
        return result

    def morph_dilate(self, mask: np.ndarray, kernel_size: int = 5, shape: str = 'ellipse') -> np.ndarray:
        """
        Dilation: grow foreground, connect nearby regions, fill small gaps

        Args:
            mask: Binary mask
            kernel_size: Size of morphological kernel
            shape: Structuring element shape (see get_kernel)

        Returns:
            Processed mask
        """
        kernel = self.get_kernel(shape, kernel_size)
        # borderValue=0: treat out-of-image as background so dilation does not
        # introduce phantom foreground sourced from the boundary constant.
        result = cv2.dilate(mask, kernel, iterations=1,
                            borderType=cv2.BORDER_CONSTANT, borderValue=0)
        self.mask = result
        return result
    
    def apply_mask_to_image(self, image: np.ndarray, mask: np.ndarray = None) -> np.ndarray:
        """
        Apply mask to image
        
        Args:
            image: Input image (RGB)
            mask: Binary mask (uses self.mask if None)
        
        Returns:
            Image with mask applied
        """
        if mask is None:
            mask = self.mask
        
        if mask is None:
            raise ValueError("未设置遮罩")
        
        # Ensure mask is 8-bit
        if mask.dtype != np.uint8:
            mask = (mask > 0).astype(np.uint8) * 255
        
        # Expand mask to 3 channels if needed
        if len(mask.shape) == 2:
            mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
        else:
            mask_3ch = mask
        
        # Apply mask
        result = cv2.bitwise_and(image, image, mask=mask)
        return result


if __name__ == '__main__':
    seg = ImageSegmentation()
    print("Segmentation module ready")
