# 开发指南

## 项目架构

### 分层设计
```
Presentation Layer (UI)
    ↓
Business Logic Layer (Core)
    ↓
Utility Layer (Utils)
    ↓
External Services (Web, Files)
```

### 核心模块

#### 1. 图像处理 (`src/core/image_processor.py`)
- 加载和保存图像
- 基本图像操作（调整大小、裁剪）
- 亮度/对比度调整
- 灰度转换

**关键方法**:
```python
processor = ImageProcessor()
image = processor.load_image('path.jpg')
processor.resize_image(800, 600)
processor.crop_region(100, 100, 500, 500)
```

#### 2. 颜色管理 (`src/core/color_manager.py`)
- 调色板管理
- 颜色匹配和量化
- 颜色数据持久化

**关键方法**:
```python
manager = ColorManager()
palette = manager.get_palette()
quantized, usage = manager.quantize_image(image, color_limit=30)
```

#### 3. 图案生成 (`src/core/pattern_generator.py`)
- 生成拼豆图案
- 图案渲染
- 物料清单生成

**关键方法**:
```python
generator = PatternGenerator()
config = PatternConfig(width_beads=50, height_beads=50)
pattern, bom = generator.generate_pattern(image, palette, config)
rendered = generator.render_pattern_with_codes(pattern, bead_size=20)
```

#### 4. 前景分割 (`src/utils/segmentation.py`)
- 多种分割算法（GrabCut、阈值处理、自适应阈值）
- 形态学操作
- 遮罩应用

**关键方法**:
```python
seg = ImageSegmentation()
mask = seg.grabcut_rect(image, x1, y1, x2, y2)
mask = seg.adaptive_threshold(image, block_size=11)
```

#### 5. 导出 (`src/utils/export.py`)
- PNG 导出（含网格、编码）
- PDF 导出（含 BOM）
- JSON/CSV 导出

**关键方法**:
```python
exporter = PatternExporter('./output')
exporter.export_png_with_codes(pattern, color_map, 'pattern')
exporter.export_pdf_pattern(pattern, color_map, bom, 'pattern')
```

#### 6. 网络爬虫 (`src/utils/web_scraper.py`)
- 从 Pixel Beads 网站抓取颜色数据
- 颜色数据持久化

**关键方法**:
```python
scraper = PixelBeadsColorScraper()
colors = scraper.fetch_colors()
```

## 开发流程

### 添加新功能

1. **确定功能位置**
   - UI 逻辑 → `src/ui/main_window.py`
   - 图像处理 → `src/core/image_processor.py`
   - 新算法 → 在 `src/utils/` 创建新模块

2. **实现功能**
   ```python
   # 示例：在 ImageProcessor 中添加新方法
   def apply_edge_detection(self) -> np.ndarray:
       """检测边缘"""
       gray = cv2.cvtColor(self.current_image, cv2.COLOR_RGB2GRAY)
       edges = cv2.Canny(gray, 100, 200)
       self.current_image = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
       return self.current_image.copy()
   ```

3. **在 UI 中集成**
   ```python
   # 在 main_window.py 中添加按钮
   edge_btn = QPushButton("边缘检测")
   edge_btn.clicked.connect(self._apply_edge_detection)
   control_panel.addWidget(edge_btn)
   
   # 添加对应的槽函数
   def _apply_edge_detection(self):
       try:
           self.image_processor.apply_edge_detection()
           image = self.image_processor.get_current_image()
           self.image_display.set_image(image)
       except Exception as e:
           QMessageBox.critical(self, "错误", str(e))
   ```

4. **测试**
   - 手动测试 UI
   - 编写单元测试

### 编写测试

```python
# tests/test_image_processor.py
import unittest
from src.core.image_processor import ImageProcessor
import numpy as np

class TestImageProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = ImageProcessor()
    
    def test_load_image(self):
        # 创建虚拟图像
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        # 测试逻辑
        
    def test_resize_image(self):
        # 测试调整大小功能

if __name__ == '__main__':
    unittest.main()
```

运行测试：
```bash
python -m pytest tests/
```

## 代码风格

### Python 风格指南 (PEP 8)
- 使用 4 个空格缩进
- 最大行长度 100 字符
- 类名使用 PascalCase
- 函数/变量名使用 snake_case
- 常量使用 UPPER_CASE

### 文档字符串
```python
def process_image(self, image: np.ndarray, factor: float) -> np.ndarray:
    """
    处理图像的简要说明。
    
    Args:
        image: 输入图像数组 (RGB)
        factor: 处理因子 (0.0-1.0)
    
    Returns:
        处理后的图像数组
    
    Raises:
        ValueError: 如果图像格式无效
    """
    pass
```

## 打包和发布

### 本地测试打包

1. **生成可执行文件**
   ```bash
   pip install pyinstaller
   pyinstaller pyinstaller.spec
   ```

2. **测试可执行文件**
   ```bash
   dist/PerlerBeadsDesigner/PerlerBeadsDesigner.exe
   ```

### 发布到 GitHub

1. **更新版本号**
   - 修改 `src/__init__.py` 中的 `__version__`
   - 修改 `setup.py` 中的 `version`

2. **创建 Git 标签**
   ```bash
   git add .
   git commit -m "Bump version to 1.1.0"
   git tag -a v1.1.0 -m "Release 1.1.0"
   git push origin v1.1.0
   ```

3. **在 GitHub 上创建 Release**
   - 去到 https://github.com/yourusername/PerlerBeadsDesigner/releases
   - 点击 "Create a new release"
   - 选择标签 v1.1.0
   - 上传 `.exe` 文件

## 常见任务

### 添加新的图像过滤器

```python
# 1. 在 ImageProcessor 中添加方法
def apply_gaussian_pyramid(self, levels: int = 3) -> np.ndarray:
    """应用高斯金字塔"""
    current = self.current_image.copy()
    for _ in range(levels):
        current = cv2.pyrDown(current)
    self.current_image = current
    return self.current_image.copy()

# 2. 在 UI 中添加控制器
level_spinbox = QSpinBox()
level_spinbox.setRange(1, 5)
pyramid_btn = QPushButton("应用高斯金字塔")
pyramid_btn.clicked.connect(self._apply_pyramid)

# 3. 实现槽函数
def _apply_pyramid(self):
    try:
        levels = self.level_spinbox.value()
        self.image_processor.apply_gaussian_pyramid(levels)
        image = self.image_processor.get_current_image()
        self.image_display.set_image(image)
    except Exception as e:
        QMessageBox.critical(self, "错误", str(e))
```

### 支持新的输出格式

```python
# 在 PatternExporter 中添加方法
def export_svg(self, pattern: np.ndarray, filename: str) -> str:
    """导出为 SVG 格式"""
    # 使用 svgwrite 库
    # ...
    return filepath

# 在 main_window.py 中添加按钮
svg_btn = QPushButton("导出SVG")
svg_btn.clicked.connect(self._export_svg)
```

## 调试技巧

### 打印调试
```python
import logging

logger = logging.getLogger(__name__)
logger.debug("调试信息")
logger.info("信息")
logger.warning("警告")
logger.error("错误")
```

### 设置日志
```python
# 在 main.py 中
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### VS Code 调试
- 设置断点：点击行号左侧
- F10：单步执行
- F11：进入函数
- Shift+F11：跳出函数
- 在 "调试控制台" 中执行表达式

## 性能优化

### 图像处理优化
```python
# 使用 numpy 的向量化操作
# 改进前
for i in range(height):
    for j in range(width):
        image[i, j] = image[i, j] * factor

# 改进后
image = image.astype(np.float32) * factor
image = np.clip(image, 0, 255).astype(np.uint8)
```

### 缓存优化
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_closest_color(self, rgb_tuple):
    # 缓存最常用的颜色搜索结果
    pass
```

## 故障排除

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| ModuleNotFoundError | 依赖未安装 | `pip install -r requirements.txt` |
| TypeError: 'NoneType' | 未加载图像 | 检查加载顺序 |
| MemoryError | 图像过大 | 在加载前调整大小 |
| ImportError: No module named 'PyQt6' | PyQt6 未安装 | `pip install PyQt6` |

### 日志查看
```bash
# Windows
type debug.log

# macOS/Linux
cat debug.log
tail -f debug.log  # 实时查看
```

## 贡献流程

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 参考资源

- [OpenCV 文档](https://docs.opencv.org/)
- [PyQt6 文档](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [NumPy 文档](https://numpy.org/doc/)
- [scikit-image 文档](https://scikit-image.org/)

祝开发愉快! 💻
