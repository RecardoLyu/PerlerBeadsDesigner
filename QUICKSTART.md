# 快速开始指南

## 1. 环境设置 (5分钟)

### Windows 用户

1. 打开 PowerShell 或 cmd，导航到项目目录：
   ```powershell
   cd d:\WS\PYTHON\PerlerBeadsDesigner
   ```

2. 创建虚拟环境：
   ```powershell
   python -m venv venv
   ```

3. 激活虚拟环境：
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

4. 安装依赖：
   ```powershell
   pip install -r requirements.txt
   ```

### macOS / Linux 用户

1. 打开终端，导航到项目目录：
   ```bash
   cd ~/path/to/PerlerBeadsDesigner
   ```

2. 创建虚拟环境：
   ```bash
   python3 -m venv venv
   ```

3. 激活虚拟环境：
   ```bash
   source venv/bin/activate
   ```

4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 2. 运行应用 (1分钟)

```bash
# 确保虚拟环境已激活
python -m src.webapp.main
```

（等价命令：`python run.py`，或直接双击 `run.bat` / `run.sh`。）

## 3. 在 VS Code 中调试

1. 在 VS Code 中打开项目文件夹
2. 安装 Python 扩展（如果还未安装）
3. 按 `F5` 或点击 "运行和调试" 按钮
4. 选择 "Python: Main Application" 配置

## 4. 基本使用步骤

### 第一次使用

1. **加载图像**
   - 切换到 "图像加载和处理" 标签页
   - 点击 "加载图像"
   - 选择你的图像文件

2. **生成图案**
   - 切换到 "图案生成" 标签页
   - 设置拼豆尺寸（例如 50x50）
   - 点击 "生成图案"

3. **渲染预览**
   - 点击 "带编码渲染" 查看带颜色代码的图案
   - 查看 "物料清单" 了解所需的拼豆数量

4. **导出结果**
   - 切换到 "导出" 标签页
   - 选择导出格式（PNG 或 PDF）
   - 点击导出按钮

## 常见快捷键

| 操作 | 快捷键 |
|------|--------|
| 开始调试 | F5 |
| 停止调试 | Shift + F5 |
| 继续执行 | F5 |
| 单步执行 | F10 |
| 进入函数 | F11 |

## 文件结构速览

```
src/
├── webapp/
│   ├── main.py          ← 应用入口，从这里开始（FastAPI + pywebview）
│   ├── app.py           ← FastAPI 路由与静态挂载
│   ├── state.py         ← 会话状态
│   └── codecs.py        ← 图像编解码
├── core/
│   ├── image_processor.py   ← 图像处理
│   ├── color_manager.py     ← 颜色管理
│   └── pattern_generator.py ← 图案生成
└── utils/
    ├── segmentation.py ← 前景分割
    └── export.py      ← 导出功能
```

## 有用的命令

```bash
# 测试导入（确保依赖安装正确）
python -c "import cv2, fastapi, uvicorn, webview; print('Dependencies OK')"

# 运行应用
python -m src.webapp.main

# 运行单个模块（测试）
python -m src.core.color_manager

# 清理缓存
rm -r src/__pycache__  # Linux/macOS
rmdir /s src\__pycache__  # Windows
```

## 快速修复常见问题

### 导入错误
```bash
# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

### 窗口不弹出 / 界面白屏

pywebview 通过本地 FastAPI 服务加载界面，窗口不显示或白屏时可按以下排查：

```bash
# 1. 重新安装 pywebview
pip uninstall pywebview -y
pip install pywebview
```

2. **检查端口占用**：应用默认占用本地端口，若被其他程序占用会导致连不上。换个端口或关闭占用进程后重试。
3. **检查防火墙 / 杀毒软件**：确认未阻止 Python 进程访问 `127.0.0.1`。
4. **查看错误日志**：服务器启动失败时会在项目根目录写入 `webapp_error.log`，打开它能看到具体报错。

### 图像无法加载
```bash
# 检查 OpenCV 是否正确安装
python -c "import cv2; print(cv2.__version__)"
```

## 下一步

- 阅读 [README.md](README.md) 了解完整功能
- 查看 [开发指南](DEVELOPMENT.md)
- 在 GitHub 上创建 issue 反馈问题

祝你使用愉快! 🎨
