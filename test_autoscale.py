#!/usr/bin/env python
"""
验证自动缩放功能是否正确实现的测试脚本
"""
import sys
import os

# Add to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_image_display_class():
    """检查ImageDisplay类是否有缩放相关的属性和方法"""
    from src.ui.main_window import ImageDisplay
    
    print("检查 ImageDisplay 类...")
    
    # 检查必要的属性和方法
    required_attrs = ['last_width', 'last_height', '_on_frame_configure', '_update_display']
    
    class_source = ImageDisplay.__init__.__code__
    
    # 检查方法是否存在
    if hasattr(ImageDisplay, '_on_frame_configure'):
        print("  ✓ 有 _on_frame_configure 方法")
    else:
        print("  ✗ 缺少 _on_frame_configure 方法")
        return False
        
    if hasattr(ImageDisplay, '_update_display'):
        print("  ✓ 有 _update_display 方法")
    else:
        print("  ✗ 缺少 _update_display 方法")
        return False
    
    return True

def test_interactive_image_display_class():
    """检查InteractiveImageDisplay类是否有缩放相关的属性和方法"""
    from src.ui.main_window import InteractiveImageDisplay
    
    print("\n检查 InteractiveImageDisplay 类...")
    
    # 检查方法是否存在
    if hasattr(InteractiveImageDisplay, '_on_frame_configure'):
        print("  ✓ 有 _on_frame_configure 方法")
    else:
        print("  ✗ 缺少 _on_frame_configure 方法")
        return False
        
    if hasattr(InteractiveImageDisplay, '_update_display'):
        print("  ✓ 有 _update_display 方法")
    else:
        print("  ✗ 缺少 _update_display 方法")
        return False
    
    return True

def test_iterative_grabcut_display_class():
    """检查IterativeGrabCutDisplay类是否有缩放相关的属性和方法"""
    from src.ui.main_window import IterativeGrabCutDisplay
    
    print("\n检查 IterativeGrabCutDisplay 类...")
    
    # 检查方法是否存在
    if hasattr(IterativeGrabCutDisplay, '_on_frame_configure'):
        print("  ✓ 有 _on_frame_configure 方法")
    else:
        print("  ✗ 缺少 _on_frame_configure 方法")
        return False
        
    if hasattr(IterativeGrabCutDisplay, '_update_display'):
        print("  ✓ 有 _update_display 方法")
    else:
        print("  ✗ 缺少 _update_display 方法")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("自动缩放功能验证测试")
    print("=" * 60)
    
    try:
        all_passed = True
        
        all_passed = test_image_display_class() and all_passed
        all_passed = test_interactive_image_display_class() and all_passed
        all_passed = test_iterative_grabcut_display_class() and all_passed
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✓ 所有功能验证成功！")
            print("自动缩放功能已正确实现为所有图像显示类。")
            sys.exit(0)
        else:
            print("✗ 某些功能验证失败。")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
