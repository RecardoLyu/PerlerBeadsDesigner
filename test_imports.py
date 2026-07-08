"""
Test script to verify all imports and dependencies
Run this to diagnose import issues
"""
import sys
import os

# Add project root to path (same as in main.py)
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

print("=" * 60)
print("Dependencies Test")
print("=" * 60)

# Test Python version
print(f"\n✓ Python version: {sys.version}")

# Test PyQt6
try:
    from PyQt6.QtWidgets import QApplication
    print("✓ PyQt6 imported successfully")
except ImportError as e:
    print(f"✗ PyQt6 import failed: {e}")

# Test NumPy
try:
    import numpy
    print("✓ NumPy imported successfully")
except ImportError as e:
    print(f"✗ NumPy import failed: {e}")

# Test OpenCV
try:
    import cv2
    print("✓ OpenCV imported successfully")
except ImportError as e:
    print(f"✗ OpenCV import failed: {e}")

# Test Pillow
try:
    from PIL import Image
    print("✓ Pillow imported successfully")
except ImportError as e:
    print(f"✗ Pillow import failed: {e}")

# Test ReportLab
try:
    from reportlab.lib.pagesizes import A4
    print("✓ ReportLab imported successfully")
except ImportError as e:
    print(f"✗ ReportLab import failed: {e}")

# Test our modules
print("\n" + "=" * 60)
print("Application Modules Test")
print("=" * 60)

try:
    from src.core.image_processor import ImageProcessor
    print("✓ ImageProcessor module imported successfully")
except ImportError as e:
    print(f"✗ ImageProcessor import failed: {e}")
    sys.exit(1)

try:
    from src.core.color_manager import ColorManager
    print("✓ ColorManager module imported successfully")
except ImportError as e:
    print(f"✗ ColorManager import failed: {e}")
    sys.exit(1)

try:
    from src.core.pattern_generator import PatternGenerator
    print("✓ PatternGenerator module imported successfully")
except ImportError as e:
    print(f"✗ PatternGenerator import failed: {e}")
    sys.exit(1)

try:
    from src.utils.segmentation import ImageSegmentation
    print("✓ ImageSegmentation module imported successfully")
except ImportError as e:
    print(f"✗ ImageSegmentation import failed: {e}")
    sys.exit(1)

try:
    from src.utils.export import PatternExporter
    print("✓ PatternExporter module imported successfully")
except ImportError as e:
    print(f"✗ PatternExporter import failed: {e}")
    sys.exit(1)

try:
    from src.ui.main_window import MainWindow
    print("✓ MainWindow module imported successfully")
except ImportError as e:
    print(f"✗ MainWindow import failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All imports successful! You can run the application.")
print("=" * 60)
print("\nRun the application with:")
print("  python -m src.main")
print("\nOr use the launch script:")
print("  Windows:   run.bat")
print("  Linux/Mac: ./run.sh")
print("=" * 60)
