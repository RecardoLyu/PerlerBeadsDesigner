# 🚀 开始使用拼豆图纸设计器

欢迎使用 **Perler Beads Designer**！这是一个功能完整的拼豆图纸设计软件。

---

## ⚡ 极速开始 (3 分钟)

### 第 1 步：安装依赖

```bash
# 进入项目目录
cd d:\WS\PYTHON\PerlerBeadsDesigner

# 创建虚拟环境（如果还没有）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 第 2 步：启动应用

```bash
python -m src.main
```

### 第 3 步：使用应用

1. **加载图像** → 点击"加载图像"按钮选择图片
2. **生成图案** → 设置拼豆数量，点击"生成图案"
3. **导出结果** → 选择导出格式（PNG/PDF）

**完成！** 🎉

---

## 📚 详细文档

| 文档 | 内容 | 阅读时间 |
|------|------|--------|
| [QUICKSTART.md](QUICKSTART.md) | 5分钟快速指南 | 5 分钟 |
| [README.md](README.md) | 完整功能说明 | 20 分钟 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 开发指南 | 30 分钟 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 部署和发布 | 15 分钟 |

---

## 🎯 按需求选择

### 我只想使用软件
👉 [QUICKSTART.md](QUICKSTART.md)
- 安装和运行
- 基本操作
- 常见问题

### 我想了解所有功能
👉 [README.md](README.md)
- 完整功能列表
- 参数详解
- 工作流程
- 故障排除

### 我想开发和扩展
👉 [DEVELOPMENT.md](DEVELOPMENT.md)
- 项目架构
- 模块 API
- 开发流程
- 代码示例

### 我想部署或打包
👉 [DEPLOYMENT.md](DEPLOYMENT.md)
- 本地开发设置
- 打包为可执行文件
- GitHub 配置
- 版本发布

---

## 🛠️ 快速命令参考

```bash
# 运行应用
python -m src.main

# 在 VS Code 中调试 (F5)
# 自动加载 launch.json 配置

# 运行测试
python -m pytest tests/ -v

# 打包为可执行文件
pyinstaller pyinstaller.spec
# 输出: dist/PerlerBeadsDesigner/

# 使用 Makefile (Linux/Mac)
make run      # 运行
make test     # 测试
make build    # 打包
make clean    # 清理
```

---

## 📂 项目结构速览

```
PerlerBeadsDesigner/
├── src/                         # ← 源代码在这里
│   ├── main.py                  # 应用入口
│   ├── ui/main_window.py        # UI 界面
│   └── core/                    # 核心功能
│       ├── image_processor.py   # 图像处理
│       ├── color_manager.py     # 颜色管理
│       └── pattern_generator.py # 图案生成
│
├── README.md                    # ← 完整使用说明
├── QUICKSTART.md                # ← 快速开始
├── DEVELOPMENT.md               # ← 开发指南
└── DEPLOYMENT.md                # ← 部署指南
```

---

## 🎨 从图像到图纸的完整流程

```
加载图像
  ↓
[可选] 图像预处理 (大小、亮度、对比度)
  ↓
[可选] 前景分割 (GrabCut、阈值等)
  ↓
生成拼豆图案 (颜色自动匹配)
  ↓
预览渲染 (网格/编码显示)
  ↓
导出结果 (PNG/PDF/BOM)
  ↓
完成！打印使用
```

---

## 💡 常见操作示例

### 示例 1: 简单照片转拼豆图纸

```
1. 点击 "加载图像" → 选择你的照片
2. 切换到 "图案生成" 标签页
3. 设置:
   - 拼豆宽度: 50
   - 拼豆高度: 50
   - 颜色限制: 20 (可选)
4. 点击 "生成图案"
5. 点击 "带编码渲染" 查看结果
6. 切换到 "导出" 标签页
7. 点击 "导出PDF" 获得可打印的图纸
```

### 示例 2: 自定义一个特定部分

```
1. 加载主图像
2. 切换到 "前景分割" 标签页
3. 选择 "GrabCut (矩形)"
4. 调整参数
5. 点击 "执行GrabCut分割"
6. 返回 "图案生成"，生成仅包含该部分的图案
```

---

## 🔧 开发者快速参考

### 运行和调试

```bash
# 方法 1: 直接运行
python -m src.main

# 方法 2: VS Code 调试 (按 F5)
# 自动加载 .vscode/launch.json

# 方法 3: Python 交互
python
>>> from src.core.image_processor import ImageProcessor
>>> processor = ImageProcessor()
>>> processor.load_image('photo.jpg')
```

### 常用类和方法

```python
# 图像处理
from src.core.image_processor import ImageProcessor
processor = ImageProcessor()
image = processor.load_image('image.jpg')
processor.resize_image(800, 600)

# 颜色管理
from src.core.color_manager import ColorManager
color_mgr = ColorManager()
palette = color_mgr.get_palette()

# 图案生成
from src.core.pattern_generator import PatternGenerator, PatternConfig
generator = PatternGenerator()
config = PatternConfig(width_beads=50, height_beads=50)
pattern, bom = generator.generate_pattern(image, palette, config)

# 导出
from src.utils.export import PatternExporter
exporter = PatternExporter('./output')
exporter.export_png_with_codes(pattern, color_map, 'result')
```

---

## ❓ 如何获得帮助

### 问题或建议

1. **查看文档**
   - [README.md](README.md) - 常见问题部分
   - [QUICKSTART.md](QUICKSTART.md) - 快速修复

2. **搜索 GitHub Issues**
   - 访问项目 GitHub 主页
   - 查看已解决的问题

3. **创建新 Issue**
   - 描述问题或建议
   - 包含错误信息（如有）

4. **联系开发者**
   - Email: your.email@example.com

---

## 🌟 功能亮点

✨ **智能颜色识别** - 自动匹配最接近的拼豆颜色

✨ **多种分割算法** - GrabCut、阈值处理、自适应等

✨ **灵活导出** - PNG、PDF、JSON、CSV 多种格式

✨ **物料清单** - 清晰的 BOM，知道每种颜色需要多少

✨ **跨平台** - Windows、macOS、Linux 都支持

✨ **生产就绪** - 完整的错误处理和文档

---

## 📋 系统要求

- **Python**: 3.8+
- **操作系统**: Windows 10+, macOS 10.14+, 或 Linux
- **内存**: 4GB RAM
- **磁盘**: 500MB 可用空间

---

## 🎓 学习资源

### 内部文档
- [代码架构](DEVELOPMENT.md#项目架构)
- [API 文档](DEVELOPMENT.md#核心模块)
- [代码示例](DEVELOPMENT.md#开发流程)

### 外部参考
- [OpenCV 文档](https://docs.opencv.org/)
- [PyQt6 官网](https://www.riverbankcomputing.com/software/pyqt/)
- [NumPy 教程](https://numpy.org/doc/stable/user/)

---

## 🚀 后续步骤

### 对普通用户
1. ✅ 安装并运行应用
2. 🔄 创建你的第一个拼豆图案
3. 📤 导出并打印
4. 🎨 开始拼豆创作！

### 对开发者
1. ✅ 克隆源代码
2. 📚 阅读 [DEVELOPMENT.md](DEVELOPMENT.md)
3. 🔧 修改或扩展功能
4. 📤 提交 Pull Request

### 对维护者
1. ✅ 部署应用
2. 📦 打包可执行文件
3. 🚀 发布到 GitHub
4. 👥 与用户互动

---

## 📞 支持和反馈

- 🐛 **发现 Bug**？ → [GitHub Issues](https://github.com/yourusername/PerlerBeadsDesigner/issues)
- 💡 **功能建议**？ → [GitHub Discussions](https://github.com/yourusername/PerlerBeadsDesigner/discussions)
- 💬 **一般问题**？ → 阅读 [README.md](README.md#故障排除)

---

## 📄 许可证

本项目采用 **MIT License**。您可以自由使用、修改、分发。

详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

感谢以下项目的支持:
- [OpenCV](https://opencv.org/)
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [NumPy](https://numpy.org/)
- [ReportLab](https://www.reportlab.com/)

---

## 版本信息

**当前版本**: 1.0.0  
**发布日期**: 2024-02-10  
**完成度**: 100% ✅

---

## 快速导航

| 链接 | 描述 |
|------|------|
| [README.md](README.md) | 完整功能文档 |
| [QUICKSTART.md](QUICKSTART.md) | 5分钟快速开始 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 开发人员指南 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 部署和发布指南 |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | 项目完成总结 |
| [CHECKLIST.md](CHECKLIST.md) | 项目完整性检查 |

---

祝您使用愉快！🎉

有任何问题，请查阅相关文档或提出 Issue。

享受创作过程！🎨✨
