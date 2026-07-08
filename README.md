# 拼豆图纸设计器 (Perler Beads Designer)

一个强大的 Python 应用程序，用于将图像转换为拼豆图纸设计。支持前景分割、颜色量化、多种导出格式。

## 功能特性

### 核心功能
- **图像加载和处理**
  - 加载 JPG、PNG、BMP 等常见格式图像
  - 调整图像大小（缩放）
  - 亮度和对比度调整
  - 灰度转换

- **前景分割与裁剪**
  - GrabCut 算法前景分割（基于矩形 ROI）
  - 自适应阈值处理
  - 简单阈值处理
  - 颜色范围选择
  - 形态学操作（开运算、闭运算）
  - 鼠标矩形选区裁剪

- **图案生成**
  - 自动将图像转换为拼豆图案
  - 可自定义拼豆数量（宽度×高度）
  - 颜色数量限制选项
  - 支持来自 Pixel Beads 官网的真实颜色库
  - 自动颜色匹配和量化

- **渲染选项**
  - 网格渲染（默认，便于计数）
  - 带颜色代码（如 A1、B2 等）和网格线的渲染
  - 自定义拼豆显示尺寸

- **导出功能**
  - **一键导出**：复选框勾选所需格式后统一导出
  - **PNG 格式**
    - 网格版
    - 带编码标签+网格版（如 A1、B2）
    - 自定义缩放倍数
  - **PDF 格式**
    - 完整的可打印图纸
    - 包含物料清单 (BOM)
    - A4 或 Letter 纸张大小
  - **物料清单 (BOM)**
    - JSON 格式
    - CSV 格式
    - 包含颜色代码、名称、数量和百分比

## 系统要求

- Python 3.8 或更高版本
- Windows 10+ / macOS 10.14+ / Linux (Ubuntu 18.04+)
- 4GB RAM
- 500MB 硬盘空间

## 安装

### 方法 1：从源代码安装（开发模式）

#### 前置条件
- 安装 Python 3.8+
- 安装 pip 包管理器

#### 步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/yourusername/PerlerBeadsDesigner.git
   cd PerlerBeadsDesigner
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   # Windows
   python -m venv venv
   venv\\Scripts\\activate
   
   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **运行应用**
   ```bash
   python -m src.main
   ```

### 方法 2：直接运行可执行文件

从 [Releases](https://github.com/yourusername/PerlerBeadsDesigner/releases) 页面下载最新的 `.exe` 文件，双击即可运行。

## 使用指南

### 基本工作流程

1. **加载图像**
   - 点击 "图像加载和处理" 标签页
   - 点击 "加载图像" 按钮
   - 选择要处理的图像文件

2. **预处理（可选）**
   - 调整图像大小
   - 微调亮度和对比度
   - 重置为原图（使用 "重置为原图" 按钮）

3. **前景分割（可选）**
   - 切换到 "前景分割" 标签页
   - 选择分割方法
   - 调整参数并应用
   - 使用形态学操作改进分割结果

4. **生成图案**
   - 切换到 "图案生成" 标签页
   - 设置拼豆宽度和高度
   - 可选：限制颜色数量
   - 点击 "生成图案"

5. **渲染和查看**
   - 默认显示网格版本（预览自动填满窗口）
   - 点击 "带编码渲染" 查看带颜色代码和网格线的版本
   - 在 "物料清单 (BOM)" 区域查看所需织珠数量

6. **导出**
   - 切换到 "导出" 标签页
   - 可选：更改输出目录
   - 勾选需要导出的格式（PNG / PDF / BOM 等，PDF 默认勾选）
   - 点击 "一键导出" 同时导出所有已勾选文件

### 参数说明

#### 图像处理参数
- **宽度 / 高度**: 调整图像尺寸（单位：像素）
- **亮度**: 1.0 = 正常，> 1.0 更亮，< 1.0 更暗
- **对比度**: 1.0 = 正常，> 1.0 更高，< 1.0 更低

#### 分割参数
- **阈值**: 0-255，值越大越容易被分割为白色
- **核大小**: 形态学操作的核尺寸，奇数效果更好

#### 图案参数
- **拼豆宽度 / 高度**: 最终图案的尺寸（单位：拼豆数）
- **颜色数量限制**: 0 = 无限制，使用尽可能多的颜色；> 0 = 限制为指定数量

#### 导出参数
- **缩放倍数**: PNG 导出的缩放倍数（1-10）
- **拼豆像素大小**: 每个拼豆在屏幕上显示的像素大小（5-100）
- **纸张大小**: PDF 导出的纸张大小（A4 或 Letter）

## 项目结构

```
PerlerBeadsDesigner/
├── src/                          # 源代码
│   ├── __init__.py
│   ├── main.py                   # 应用入口
│   ├── ui/                       # 用户界面
│   │   ├── __init__.py
│   │   └── main_window.py        # 主窗口
│   ├── core/                     # 核心功能
│   │   ├── __init__.py
│   │   ├── image_processor.py    # 图像处理
│   │   ├── color_manager.py      # 颜色管理
│   │   └── pattern_generator.py  # 图案生成
│   ├── utils/                    # 实用工具
│   │   ├── __init__.py
│   │   ├── segmentation.py       # 前景分割
│   │   ├── export.py             # 导出功能
│   │   └── web_scraper.py        # 网络爬虫
│   └── assets/                   # 资源文件
│       └── colors.json           # 颜色配置
├── tests/                        # 单元测试
├── resources/                    # 资源文件
│   └── icons/                    # 图标（待添加）
├── requirements.txt              # Python 依赖
├── setup.py                      # 安装脚本
├── pyinstaller.spec              # PyInstaller 配置
├── .gitignore                    # Git 忽略文件
├── README.md                     # 本文件
└── LICENSE                       # 许可证

```

## 颜色库

程序使用 MARD 221 色拼豆颜色库进行颜色匹配。支持多种颜色距离算法：

- **加权距离**（默认）：基于亮度的加权欧氏距离（R:G:B = 3:6:1），符合人眼感知特性
- **欧氏距离**：标准 RGB 欧氏距离
- **Lab 色空间**：在 CIE LAB 色空间中的欧氏距离
- **CIE76**：CIE LAB 色空间的 ΔE 距离

## 开发和打包

### 开发环境设置

1. **克隆仓库**
   ```bash
   git clone https://github.com/yourusername/PerlerBeadsDesigner.git
   cd PerlerBeadsDesigner
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   ```

3. **激活虚拟环境**
   ```bash
   # Windows
   venv\\Scripts\\activate
   # macOS / Linux
   source venv/bin/activate
   ```

4. **安装开发依赖**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

5. **在 VS Code 中调试**
   - 打开项目文件夹
   - 安装 Python 扩展
   - 创建 `.vscode/launch.json`:
     ```json
     {
         "version": "0.2.0",
         "configurations": [
             {
                 "name": "Python: Main",
                 "type": "python",
                 "request": "launch",
                 "program": "${workspaceFolder}/src/main.py",
                 "console": "integratedTerminal",
                 "justMyCode": true
             }
         ]
     }
     ```
   - 按 F5 开始调试

### 打包为可执行文件

#### 使用 PyInstaller

1. **安装 PyInstaller**
   ```bash
   pip install pyinstaller
   ```

2. **生成可执行文件**
   ```bash
   pyinstaller pyinstaller.spec
   ```

3. **输出位置**
   - 可执行文件位于 `dist/PerlerBeadsDesigner/` 目录
   - Windows 用户可直接双击 `PerlerBeadsDesigner.exe` 运行

4. **创建安装程序**
   ```bash
   pip install pyinstaller nsis
   # 使用 NSIS 创建 Windows 安装程序
   ```

#### 单文件可执行文件

如需生成单个 `.exe` 文件，修改 `pyinstaller.spec`：
```python
exe = EXE(
    ...,
    name='PerlerBeadsDesigner',
    onefile=True,  # 添加此行
    ...
)
```

然后重新运行 `pyinstaller pyinstaller.spec`。

## Git 版本管理

### 初始化与提交

1. **初始化仓库**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Perler Beads Designer v1.0.0"
   ```

2. **添加远程仓库**
   ```bash
   git remote add origin https://github.com/yourusername/PerlerBeadsDesigner.git
   ```

3. **推送到 GitHub**
   ```bash
   git branch -M main
   git push -u origin main
   ```

### 工作流程

```bash
# 创建特性分支
git checkout -b feature/new-feature

# 做出更改
# ...

# 提交更改
git add .
git commit -m "description of changes"

# 推送分支
git push origin feature/new-feature

# 创建 Pull Request 并合并到 main
```

### 发布新版本

```bash
# 创建版本标签
git tag -a v1.1.0 -m "Release version 1.1.0"

# 推送标签
git push origin v1.1.0

# 在 GitHub Releases 中创建新版本，上传 .exe 文件
```

## 故障排除

### 问题：无法加载图像
- **解决方案**: 确保图像格式支持（JPG、PNG、BMP），文件未损坏

### 问题：前景分割效果不理想
- 尝试调整阈值值
- 使用不同的分割方法
- 预处理图像（调整亮度/对比度）

### 问题：颜色加载失败
- 检查网络连接
- 程序会自动使用默认颜色库

### 问题：导出 PDF 出错
- 确保输出目录有写入权限
- 检查磁盘空间

### 问题：PyInstaller 打包失败
- 清除旧的构建目录：`rm -rf build/ dist/`
- 重新生成：`pyinstaller pyinstaller.spec`

## API 文档

### 关键类

#### ColorManager
```python
from src.core.color_manager import ColorManager

manager = ColorManager()
palette = manager.get_palette()
closest_color = palette.get_closest_color((255, 0, 0))
```

#### ImageProcessor
```python
from src.core.image_processor import ImageProcessor

processor = ImageProcessor()
image = processor.load_image('image.jpg')
processor.resize_image(800, 600)
```

#### PatternGenerator
```python
from src.core.pattern_generator import PatternGenerator, PatternConfig

generator = PatternGenerator()
config = PatternConfig(width_beads=50, height_beads=50)
pattern, bom = generator.generate_pattern(image, palette, config)
```

#### PatternExporter
```python
from src.utils.export import PatternExporter

exporter = PatternExporter('./output')
exporter.export_png(pattern, 'pattern', scale=2)
exporter.export_pdf_pattern(pattern, color_map, bom, 'pattern', 'A4')
```

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- Email: your.email@example.com
- GitHub: https://github.com/yourusername

## 致谢

- 感谢 [Pixel Beads](https://www.pixel-beads.com) 提供真实的拼豆颜色库
- 使用 OpenCV、PyQt6、numpy 等开源库

---

**最后更新**: 2025 年
**版本**: 1.1.0
