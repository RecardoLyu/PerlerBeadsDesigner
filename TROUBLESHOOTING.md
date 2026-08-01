# 快速故障排除指南

## ❌ 错误：ModuleNotFoundError: No module named 'src'

### 🔍 问题诊断

这个错误说明 Python 的模块搜索路径没有正确包含项目根目录。

**常见原因：**
1. 从子目录（如 src/webapp/ 目录）运行应用
2. 使用 `python src/webapp/main.py` 而不是 `python -m src.webapp.main`
3. 工作目录不是项目根目录

### ✅ 解决方案

#### 最简单的方法：使用启动脚本

**Windows:**
```bash
run.bat
```

**macOS/Linux:**
```bash
chmod +x run.sh
./run.sh
```

#### 手动修复

1. **确保当前目录正确**
   ```bash
   # 应该在包含 src 文件夹的目录
   cd d:\WS\PYTHON\PerlerBeadsDesigner
   # 验证
   dir              # Windows
   ls               # macOS/Linux
   # 应该看到 src/ 目录
   ```

2. **激活虚拟环境**
   ```bash
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **运行应用**
   ```bash
   python -m src.webapp.main
   ```

### 🧪 验证导入

运行导入测试脚本来诊断具体问题：

```bash
python test_imports.py
```

这会显示：
- ✓ 所有依赖是否正确安装
- ✓ 所有应用模块是否可以导入
- ✗ 如果有失败，会显示具体错误信息

### 📋 完整检查清单

- [ ] 虚拟环境已创建：`venv/` 目录存在
- [ ] 虚拟环境已激活：命令行显示 `(venv)` 前缀
- [ ] 依赖已安装：`pip list` 包含 fastapi、uvicorn、pywebview、numpy、opencv-python
- [ ] 当前目录是项目根目录：`ls src/` 或 `dir src` 有输出
- [ ] 使用正确的命令：`python -m src.webapp.main` 而不是 `python src/webapp/main.py`

---

## ❌ 其他常见错误

### Q: 找不到 requirements.txt
**A:** 确认你在项目根目录，不是在 src 目录或其他子目录

### Q: pip 安装失败
**A:** 
```bash
# 清除缓存重新安装
pip install --force-reinstall -r requirements.txt

# 或升级 pip
python -m pip install --upgrade pip
```

### Q: pywebview / FastAPI 导入失败
**A:**
```bash
pip install --force-reinstall pywebview fastapi uvicorn
```

### Q: OpenCV 导入失败
**A:**
```bash
# 某些系统可能需要系统库
# Windows: 通常直接安装即可
pip install opencv-python

# macOS: 
pip install opencv-python

# Linux:
pip install opencv-python
# 如果仍然失败，需要系统库支持
```

### Q: 应用启动后立即崩溃
**A:** 检查错误消息：
```bash
# 运行应用并查看错误
python -m src.webapp.main

# 或在 VS Code 中按 F5 调试，查看控制台输出
```

### Q: 窗口不弹出或出现白屏
**A:** 这是 Web 视图相关的问题，按以下顺序排查：
1. 查看启动错误日志：开发运行时看项目根目录下的 `webapp_error.log`；如果是打包后的 exe，则看 exe 同目录下的 `webapp_error.log`
2. 检查本地端口是否被占用（应用会在本机启动一个 FastAPI 服务）
3. 检查防火墙/安全软件是否拦截了本地回环端口或 pywebview 窗口
4. 确认 pywebview 已正确安装：
   ```bash
   python -c "import fastapi, uvicorn, webview; print('OK')"
   ```

---

## 🎯 验证修复

运行以下命令验证问题已解决：

```bash
# 1. 测试所有导入
python test_imports.py
# 输出：✓ All imports successful!

# 2. 启动应用
python -m src.webapp.main
# 应该看到拼豆设计器窗口（内嵌 Web 视图）出现
```

---

## 📞 进一步帮助

1. 查看 [HOW_TO_RUN.md](HOW_TO_RUN.md) 了解不同平台的运行方式
2. 查看 [README.md](README.md#故障排除) 的完整故障排除部分
3. 查看 [QUICKSTART.md](QUICKSTART.md) 了解基本使用
4. 查看 [DEVELOPMENT.md](DEVELOPMENT.md) 了解开发设置

---

## 🔑 关键命令速查表

```bash
# 一步启动（推荐）
run.bat              # Windows
./run.sh             # macOS/Linux

# 多步手动启动
python -m venv venv                      # 创建虚拟环境
.\venv\Scripts\activate                  # Windows 激活
source venv/bin/activate                 # macOS/Linux 激活
pip install -r requirements.txt          # 安装依赖
python -m src.webapp.main                # 运行应用

# 诊断
python test_imports.py                   # 测试导入
python -c "from src import *; print('OK')"  # 快速测试
```

---

**最常见的解决方案：**

```bash
# 如果所有其他方法都不行，尝试这个
cd d:\WS\PYTHON\PerlerBeadsDesigner
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m src.webapp.main
```

**祝您使用愉快！** 🎉
