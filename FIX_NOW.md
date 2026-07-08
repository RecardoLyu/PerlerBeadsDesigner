# ⚡ 立即修复：3 分钟解决导入问题

## 🚨 问题

```
ModuleNotFoundError: No module named 'src'
```

## ✅ 一键解决

### Windows 用户

在 PowerShell 中运行：

```powershell
# 确保在项目目录
cd "d:\WS\PYTHON\PerlerBeadsDesigner"

# 一键启动（包括所有设置）
.\run.bat
```

### macOS/Linux 用户

在终端中运行：

```bash
# 确保在项目目录
cd ~/path/to/PerlerBeadsDesigner

# 一键启动（包括所有设置）
chmod +x run.sh
./run.sh
```

---

## 如果上面不行，试试这个

### 方案 B：手动 4 步启动

```bash
# 步骤 1: 进入项目目录
cd d:\WS\PYTHON\PerlerBeadsDesigner    # Windows
# 或
cd ~/path/to/PerlerBeadsDesigner       # macOS/Linux

# 步骤 2: 创建虚拟环境（首次只需一次）
python -m venv venv

# 步骤 3: 激活虚拟环境
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 步骤 4: 安装依赖（首次只需一次）
pip install -r requirements.txt

# 步骤 5: 运行应用 ⭐ 关键
python -m src.main
```

---

## ⚠️ **最重要的一点**

**使用这个命令：**
```bash
python -m src.main
```

**NOT 这个：**
```bash
python src/main.py        ❌ 错误，会导致导入失败
```

**关键区别：**
- `python -m src.main` → 告诉 Python 以模块形式运行，正确设置路径
- `python src/main.py` → 直接运行脚本，导入路径不对

---

## 🔍 验证问题已解决

运行这个测试脚本：

```bash
python test_imports.py
```

**如果看到：**
```
✓ All imports successful! You can run the application.
```

那么一切都没问题了！

---

## 🆘 如果仍然有问题

### 检查这些：

1. **确认当前目录**
   ```bash
   # 应该看到 src 目录
   ls              # macOS/Linux
   dir             # Windows
   ```

2. **检查虚拟环境**
   ```bash
   # 命令行前缀应该是 (venv)
   # 如果没有，运行：
   # Windows: .\venv\Scripts\activate
   # macOS/Linux: source venv/bin/activate
   ```

3. **检查依赖**
   ```bash
   pip list | grep PyQt6
   # 应该看到 PyQt6 的版本号
   ```

4. **查看详细错误**
   ```bash
   python -m src.main
   # 会显示详细的错误追踪
   ```

---

## 📚 需要更详细的帮助？

查看这些文档：

| 文档 | 用于 |
|------|------|
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | 各种运行方式的详细说明 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 常见错误和解决方案 |
| [QUICKSTART.md](QUICKSTART.md) | 软件基本使用 |
| [README.md](README.md) | 完整文档 |

---

## 💡 记住最关键的三点

1. **必须在项目根目录运行**（包含 src 文件夹）
2. **必须使用 `python -m src.main` 命令**（不是 `python src/main.py`）
3. **必须先激活虚拟环境**（看到 (venv) 前缀）

---

**现在就试试：** `python -m src.main` 或者 `run.bat`

**应该就能看到应用窗口了！** 🎉

有任何问题，查看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) 或 [HOW_TO_RUN.md](HOW_TO_RUN.md)。
