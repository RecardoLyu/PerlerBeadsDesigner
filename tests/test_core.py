"""
Unit tests for Perler Beads Designer
"""
import unittest
import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.image_processor import ImageProcessor
from src.core.color_manager import ColorManager, Color, ColorPalette
from src.core.pattern_generator import PatternGenerator, PatternConfig


class TestColor(unittest.TestCase):
    """Test Color class"""
    
    def test_color_initialization(self):
        color = Color('A1', 'White', '#FFFFFF')
        self.assertEqual(color.code, 'A1')
        self.assertEqual(color.name, 'White')
        self.assertEqual(color.hex, '#FFFFFF')
        self.assertEqual(color.rgb, (255, 255, 255))
    
    def test_hex_to_rgb_conversion(self):
        color = Color('B1', 'Red', '#FF0000')
        self.assertEqual(color.rgb, (255, 0, 0))
    
    def test_color_distance(self):
        color = Color('A1', 'White', '#FFFFFF')
        distance = color.distance_to((255, 255, 255))
        self.assertEqual(distance, 0)
        
        distance = color.distance_to((0, 0, 0))
        self.assertGreater(distance, 0)


class TestColorPalette(unittest.TestCase):
    """Test ColorPalette class"""
    
    def setUp(self):
        self.colors = [
            Color('A1', 'White', '#FFFFFF'),
            Color('A2', 'Black', '#000000'),
            Color('A3', 'Red', '#FF0000'),
        ]
        self.palette = ColorPalette(self.colors)
    
    def test_palette_creation(self):
        self.assertEqual(len(self.palette.colors), 3)
    
    def test_get_color(self):
        color = self.palette.get_color('A1')
        self.assertIsNotNone(color)
        self.assertEqual(color.name, 'White')
    
    def test_get_closest_color(self):
        # Should find white as closest to light gray
        closest = self.palette.get_closest_color((200, 200, 200))
        self.assertEqual(closest.code, 'A1')
        
        # Should find black as closest to dark gray
        closest = self.palette.get_closest_color((50, 50, 50))
        self.assertEqual(closest.code, 'A2')


class TestImageProcessor(unittest.TestCase):
    """Test ImageProcessor class"""
    
    def setUp(self):
        self.processor = ImageProcessor()
        # Create dummy image
        self.test_image = np.ones((100, 100, 3), dtype=np.uint8) * 128
    
    def test_image_resizing(self):
        # Manually load test image
        self.processor.current_image = self.test_image.copy()
        self.processor.original_image = self.test_image.copy()
        
        self.processor.resize_image(50, 50)
        result = self.processor.get_current_image()
        self.assertEqual(result.shape, (50, 50, 3))
    
    def test_crop_region(self):
        self.processor.current_image = self.test_image.copy()
        self.processor.original_image = self.test_image.copy()
        
        self.processor.crop_region(10, 10, 90, 90)
        result = self.processor.get_current_image()
        self.assertEqual(result.shape, (80, 80, 3))


class TestPatternConfig(unittest.TestCase):
    """Test PatternConfig"""
    
    def test_config_creation(self):
        config = PatternConfig(width_beads=50, height_beads=50, max_colors=30)
        self.assertEqual(config.width_beads, 50)
        self.assertEqual(config.height_beads, 50)
        self.assertEqual(config.max_colors, 30)


class TestColorManager(unittest.TestCase):
    """Test ColorManager"""
    
    def test_default_palette(self):
        manager = ColorManager()
        palette = manager.get_palette()
        self.assertGreater(len(palette.colors), 0)


if __name__ == '__main__':
    unittest.main()
