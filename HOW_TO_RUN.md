# 如何运行拼豆图纸设计器

## ⚠️ 常见问题：ModuleNotFoundError

如果遇到 `ModuleNotFoundError: No module named 'src'` 错误，这是因为没有从正确的目录运行应用。

---

## ✅ 正确的运行方法

### Windows 用户

#### 方法 1️⃣：使用启动脚本（推荐）

```bash
# 在项目根目录执行
run.bat
```

这个脚本会自动：
- 创建虚拟环境（如果不存在）
- 激活虚拟环境
- 安装依赖（如果需要）
- 启动应用

#### 方法 2️⃣：手动运行

确保你在 **项目根目录**（包含 `src` 文件夹的目录）：

```powershell
# 1. 创建虚拟环境（首次）
python -m venv venv

# 2. 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 3. 安装依赖（首次）
pip install -r requirements.txt

# 4. 运行应用 ⭐ 关键：使用 -m 参数
python -m src.main
```

**⚠️ 重要**：必须使用 `python -m src.main` 而不是 `python src/main.py`

#### 方法 3️⃣：在 VS Code 中调试

1. 打开项目文件夹
2. 确保 Python 扩展已安装
3. 按 `F5` 开始调试（会自动使用 `.vscode/launch.json` 配置）

---

### macOS/Linux 用户

#### 方法 1️⃣：使用启动脚本（推荐）

```bash
# 在项目根目录执行
chmod +x run.sh
./run.sh
```

#### 方法 2️⃣：手动运行

```bash
# 1. 创建虚拟环境（首次）
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 安装依赖（首次）
pip install -r requirements.txt

# 4. 运行应用 ⭐ 关键：使用 -m 参数
python -m src.main
```

#### 方法 3️⃣：在 VS Code 中调试

1. 打开项目文件夹
2. 确保 Python 扩展已安装
3. 按 `F5` 开始调试

---

## 🔍 为什么会出现导入错误？

❌ **错误方式**：
```bash
cd src
python main.py              # ❌ 错误：在 src 目录运行
# 或
python src/main.py          # ❌ 错误：工作目录不对
```

✅ **正确方式**：
```bash
# 从项目根目录运行
python -m src.main          # ✅ 正确：-m 参数告诉 Python 执行模块
```

---

## 📂 确认工作目录

运行应用前，确认你在正确的目录：

```bash
# 应该看到以下文件和目录
ls -la
# 输出：
# src/
# tests/
# requirements.txt
# setup.py
# run.bat
# run.sh
# README.md
# ... 其他文件
```

---

## 🆘 如果仍然有问题

### 检查清单

- [ ] 当前目录是项目根目录（包含 `src` 文件夹）
- [ ] 已激活虚拟环境（Windows 会显示 `(venv)` 前缀）
- [ ] 已安装依赖：`pip list | grep PyQt6`
- [ ] 使用了 `python -m src.main` 命令

### 调试步骤

```python
# 1. 检查 Python 版本
python --version      # 应该是 3.8+

# 2. 检查依赖安装
pip list              # 应该看到 PyQt6、numpy、opencv-python 等

# 3. 测试导入
python -c "import PyQt6; print('PyQt6 OK')"
python -c "import cv2; print('OpenCV OK')"
python -c "import numpy; print('NumPy OK')"

# 4. 测试模块
python -c "from src.core.color_manager import ColorManager; print('Import OK')"
```

### 重新安装依赖

```bash
# 清除缓存并重新安装
pip install --force-reinstall -r requirements.txt
```

---

## 📱 快速命令卡片

保存此部分以便快速参考：

```bash
# Windows
run.bat                       # 一键启动

# macOS/Linux
chmod +x run.sh && ./run.sh   # 一键启动

# 或手动运行（任何平台）
python -m src.main            # 从项目根目录运行
```

---

## 🎯 下一步

应用启动后，你会看到一个 PyQt6 窗口。然后：

1. 点击 "加载图像" 加载一张图片
2. 在"图案生成"标签页设置拼豆数量
3. 点击 "生成图案"
4. 查看物料清单和导出选项

---

**有任何问题，查看 [README.md](README.md#故障排除) 的故障排除部分！**
