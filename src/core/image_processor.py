"""
Image processing module for Perler Beads Designer
"""
import cv2
import numpy as np
from typing import Tuple, Optional
import os


class ImageProcessor:
    """Handles image loading, manipulation, and basic processing"""
    
    def __init__(self):
        self.original_image = None
        self.current_image = None
        self.image_path = None
    
    def load_image(self, filepath: str) -> np.ndarray:
        """
        Load image from file
        
        Args:
            filepath: Path to image file
        
        Returns:
            Image array in RGB format
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"图像文件不存在: {filepath}")
        
        # Load with OpenCV (BGR format)
        image = cv2.imread(filepath)
        if image is None:
            raise ValueError(f"无法加载图像: {filepath}")
        
        # Convert BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        self.original_image = image.copy()
        self.current_image = image.copy()
        self.image_path = filepath
        
        return self.current_image.copy()
    
    def get_current_image(self) -> np.ndarray:
        """Get current working image"""
        if self.current_image is None:
            raise ValueError("未加载图像")
        return self.current_image.copy()
    
    def get_original_image(self) -> np.ndarray:
        """Get original image"""
        if self.original_image is None:
            raise ValueError("未加载图像")
        return self.original_image.copy()
    
    def reset_to_original(self) -> np.ndarray:
        """Reset to original image"""
        if self.original_image is None:
            raise ValueError("未加载图像")
        self.current_image = self.original_image.copy()
        return self.current_image.copy()
    
    def resize_image(self, width: int, height: int, 
                     interpolation: str = 'bilinear') -> np.ndarray:
        """
        Resize image to specified dimensions
        
        Args:
            width: Target width
            height: Target height
            interpolation: Interpolation method ('bilinear', 'nearest', 'bicubic')
        
        Returns:
            Resized image
        """
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        interp_map = {
            'nearest': cv2.INTER_NEAREST,
            'bilinear': cv2.INTER_LINEAR,
            'bicubic': cv2.INTER_CUBIC,
            'lanczos': cv2.INTER_LANCZOS4
        }
        
        interp = interp_map.get(interpolation, cv2.INTER_LINEAR)
        resized = cv2.resize(self.current_image, (width, height), interpolation=interp)
        self.current_image = resized
        return self.current_image.copy()
    
    def crop_region(self, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """
        Crop image to specified region
        
        Args:
            x1, y1: Top-left corner
            x2, y2: Bottom-right corner
        
        Returns:
            Cropped image
        """
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        # Ensure coordinates are within bounds
        h, w = self.current_image.shape[:2]
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        
        # Swap if needed
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        
        cropped = self.current_image[y1:y2, x1:x2].copy()
        self.current_image = cropped
        return self.current_image.copy()
    
    def convert_to_grayscale(self) -> np.ndarray:
        """Convert to grayscale"""
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        gray = cv2.cvtColor(self.current_image, cv2.COLOR_RGB2GRAY)
        self.current_image = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        return self.current_image.copy()
    
    def adjust_brightness(self, factor: float) -> np.ndarray:
        """
        Adjust brightness
        
        Args:
            factor: Brightness factor (0.5 = darker, 1.5 = brighter)
        
        Returns:
            Brightness-adjusted image
        """
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        adjusted = np.clip(self.current_image.astype(np.float32) * factor, 0, 255)
        self.current_image = adjusted.astype(np.uint8)
        return self.current_image.copy()
    
    def adjust_contrast(self, factor: float) -> np.ndarray:
        """
        Adjust contrast
        
        Args:
            factor: Contrast factor (0.5 = lower, 1.5 = higher)
        
        Returns:
            Contrast-adjusted image
        """
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        mean = np.mean(self.current_image)
        adjusted = np.clip((self.current_image.astype(np.float32) - mean) * factor + mean, 0, 255)
        self.current_image = adjusted.astype(np.uint8)
        return self.current_image.copy()
    
    def downscale_to_beads(self, num_beads_width: int) -> np.ndarray:
        """
        Downscale image to bead count
        
        Args:
            num_beads_width: Number of beads for width
        
        Returns:
            Downscaled image
        """
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        h, w = self.current_image.shape[:2]
        aspect_ratio = h / w
        num_beads_height = max(1, int(num_beads_width * aspect_ratio))
        
        # Use nearest neighbor for pixel-perfect scaling
        resized = cv2.resize(self.current_image, (num_beads_width, num_beads_height),
                            interpolation=cv2.INTER_NEAREST)
        self.current_image = resized
        return self.current_image.copy()
    
    def apply_gaussian_blur(self, kernel_size: int = 5) -> np.ndarray:
        """Apply Gaussian blur"""
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        # Ensure kernel size is odd
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        blurred = cv2.GaussianBlur(self.current_image, (kernel_size, kernel_size), 0)
        self.current_image = blurred
        return self.current_image.copy()
    
    def apply_bilateral_filter(self, diameter: int = 9, 
                               sigma_color: float = 75, 
                               sigma_space: float = 75) -> np.ndarray:
        """Apply bilateral filter for edge-preserving smoothing"""
        if self.current_image is None:
            raise ValueError("未加载图像")
        
        filtered = cv2.bilateralFilter(self.current_image, diameter, sigma_color, sigma_space)
        self.current_image = filtered
        return self.current_image.copy()
    
    def get_image_info(self) -> dict:
        """Get information about current image"""
        if self.current_image is None:
            return {}
        
        h, w, c = self.current_image.shape if len(self.current_image.shape) == 3 else (*self.current_image.shape, 1)
        return {
            'width': w,
            'height': h,
            'channels': c,
            'size': h * w,
            'dtype': str(self.current_image.dtype)
        }


if __name__ == '__main__':
    processor = ImageProcessor()
    # Test usage would go here
    print("ImageProcessor ready")
