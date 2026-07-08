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
    
    def morph_close(self, mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """
        Morphological closing to fill holes
        
        Args:
            mask: Binary mask
            kernel_size: Size of morphological kernel
        
        Returns:
            Processed mask
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        result = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        self.mask = result
        return result
    
    def morph_open(self, mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """
        Morphological opening to remove noise
        
        Args:
            mask: Binary mask
            kernel_size: Size of morphological kernel
        
        Returns:
            Processed mask
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        result = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
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
