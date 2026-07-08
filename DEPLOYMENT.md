# 部署指南 (DEPLOYMENT.md)

## 目录
1. [本地开发环境](#本地开发环境)
2. [打包为可执行文件](#打包为可执行文件)
3. [GitHub 配置](#github-配置)
4. [发布版本](#发布版本)
5. [用户安装](#用户安装)

---

## 本地开发环境

### 第一次设置（快速版）

#### Windows PowerShell
```powershell
# 1. 克隆仓库
git clone https://github.com/yourusername/PerlerBeadsDesigner.git
cd PerlerBeadsDesigner

# 2. 创建虚拟环境
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行应用
python -m src.main
```

#### macOS/Linux Bash
```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/PerlerBeadsDesigner.git
cd PerlerBeadsDesigner

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行应用
python -m src.main
```

### 在 VS Code 中开发

1. **打开项目**
   - File → Open Folder → 选择项目目录

2. **选择 Python 解释器**
   - Ctrl+Shift+P → "Python: Select Interpreter"
   - 选择虚拟环境中的 Python

3. **开始调试**
   - F5 或 Run → Start Debugging
   - 会启动 main.py 并支持断点调试

4. **运行测试**
   - 按 Ctrl+Shift+P → "Python: Run All Tests"
   - 或在终端运行: `python -m pytest tests/ -v`

---

## 打包为可执行文件

### 准备工作

确保已安装 PyInstaller:
```bash
pip install pyinstaller
```

### Windows 打包

#### 方法 1: 使用批处理脚本（推荐）
```bash
build.bat
```
输出路径: `dist\PerlerBeadsDesigner\PerlerBeadsDesigner.exe`

#### 方法 2: 手动打包
```bash
pyinstaller pyinstaller.spec
```

#### 验证可执行文件
```bash
dist\PerlerBeadsDesigner\PerlerBeadsDesigner.exe
```

### macOS/Linux 打包

#### 使用构建脚本
```bash
bash build.sh
```
输出路径: `dist/PerlerBeadsDesigner/PerlerBeadsDesigner`

#### 手动打包
```bash
pyinstaller pyinstaller.spec
```

#### 在 macOS 上增加执行权限
```bash
chmod +x dist/PerlerBeadsDesigner/PerlerBeadsDesigner
```

### 创建单文件可执行文件

修改 `pyinstaller.spec`，在 EXE 配置中添加 `onefile=True`:

```python
exe = EXE(
    pyz,
    a.scripts,
    # ... 其他参数
    name='PerlerBeadsDesigner',
    onefile=True,  # ← 添加此行
    # ...
)
```

然后重新打包:
```bash
pyinstaller pyinstaller.spec
```

输出文件将在 `dist/` 目录中。

---

## GitHub 配置

### 1. 初始化 Git 仓库

```bash
cd PerlerBeadsDesigner
git init
git add .
git commit -m "Initial commit: Perler Beads Designer v1.0.0"
```

### 2. 添加远程仓库

```bash
# 在 GitHub 上创建新仓库后
git remote add origin https://github.com/yourusername/PerlerBeadsDesigner.git
git branch -M main
git push -u origin main
```

### 3. 设置 GitHub Pages（可选）

在仓库设置中启用 GitHub Pages，用于项目文档。

### 4. 保护主分支

在 GitHub → Settings → Branches 中配置:
- Require pull request reviews
- Dismiss stale PR approvals
- Require branches to be up to date

### 5. 生成个人访问令牌（PAT）

用于 GitHub Actions:
1. GitHub → Settings → Developer settings → Personal access tokens
2. 点击 "Generate new token (classic)"
3. 选择 `repo` 和 `workflow` 权限
4. 复制令牌并添加到仓库秘密

### 6. 配置 Actions 秘密

在仓库 Settings → Secrets and variables → Actions 中添加:
- `GITHUB_TOKEN` (自动提供)
- 其他需要的秘密

---

## 发布版本

### 版本号管理

遵循 [语义版本](https://semver.org/lang/zh-CN/):
- MAJOR.MINOR.PATCH
- 例如: v1.0.0, v1.1.0, v1.0.1

### 发布流程

#### 1. 更新版本号

编辑以下文件:

文件: `src/__init__.py`
```python
__version__ = "1.1.0"
```

文件: `setup.py`
```python
setup(
    version="1.1.0",
    # ...
)
```

文件: `CHANGELOG.md` - 添加新版本条目

#### 2. 提交更改

```bash
git add .
git commit -m "Bump version to 1.1.0"
```

#### 3. 创建 Git 标签

```bash
git tag -a v1.1.0 -m "Release version 1.1.0

Features:
- Feature 1
- Feature 2

Bug Fixes:
- Fix 1"

git push origin v1.1.0
```

#### 4. 在 GitHub 上创建 Release

选项 A: 自动（通过 GitHub Actions）
- 标签推送后，Actions 会自动构建和上传

选项 B: 手动
1. 在 GitHub 仓库中，点击 "Releases"
2. 点击 "Create a new release"
3. 选择之前创建的标签
4. 添加发布标题和说明
5. 上传构建的可执行文件:
   - `PerlerBeadsDesigner-windows.exe`
   - `PerlerBeadsDesigner-macos`
   - `PerlerBeadsDesigner-linux`
6. 发布

### 检查发布状态

```bash
# 查看所有标签
git tag

# 查看特定标签信息
git show v1.1.0

# 查看远程标签
git ls-remote --tags origin
```

---

## 用户安装

### 方法 1: 下载可执行文件（推荐）

1. 访问 GitHub Releases 页面
2. 下载适合您操作系统的文件
3. 双击运行（Windows）或终端运行（Mac/Linux）

### 方法 2: 从源代码安装

```bash
git clone https://github.com/yourusername/PerlerBeadsDesigner.git
cd PerlerBeadsDesigner
pip install -r requirements.txt
python -m src.main
```

### 方法 3: 从 PyPI 安装（未来）

```bash
pip install perler-beads-designer
perler-beads-designer
```

### 创建桌面快捷方式

#### Windows
```bat
@echo off
REM 创建快捷方式脚本
powershell -Command "$TargetPath='C:\\Path\\To\\PerlerBeadsDesigner.exe'; $ShortcutPath='%USERPROFILE%\\Desktop\\Perler Beads Designer.lnk'; $WshShell=New-Object -ComObject WScript.Shell; $Shortcut=$WshShell.CreateShortcut($ShortcutPath); $Shortcut.TargetPath=$TargetPath; $Shortcut.Save()"
```

#### macOS
```bash
# 创建应用程序快捷方式
mkdir -p ~/Applications
cp -r dist/PerlerBeadsDesigner/PerlerBeadsDesigner ~/Applications/
ln -sf ~/Applications/PerlerBeadsDesigner ~/Applications/'Perler Beads Designer'
```

#### Linux
```bash
# 创建桌面项目
cat > ~/.local/share/applications/perler-beads.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Perler Beads Designer
Exec=/path/to/PerlerBeadsDesigner
Icon=image-x-generic
Categories=Graphics;
EOF
```

---

## 故障排除

### 打包相关问题

#### q: PyInstaller 提示找不到模块
**A**: 在 `pyinstaller.spec` 中的 `hiddenimports` 添加模块名称

#### Q: 可执行文件很大（> 500MB）
**A**: 这是正常的。可以考虑:
- 使用 UPX 压缩
- 删除不需要的库
- 使用 `--onefile` 但仍会很大

#### Q: 运行可执行文件时报错
**A**: 
1. 确保所有依赖已安装
2. 检查 Python 路径
3. 查看控制台输出错误信息

### 网络问题

#### Q: 无法抓取拼豆颜色库
**A**: 
1. 检查网络连接
2. 应用会自动使用默认颜色库
3. 手动更新颜色库:
```python
from src.utils.web_scraper import PixelBeadsColorScraper
scraper = PixelBeadsColorScraper()
colors = scraper.fetch_colors()
```

### GitHub 相关问题

#### Q: Actions 构建失败
**A**: 
1. 检查 `.github/workflows/build.yml`
2. 查看 Actions 日志
3. 确保所有依赖都在 `requirements.txt` 中

#### Q: Release 没有自动创建
**A**:
1. 检查标签是否正确推送: `git push origin v1.0.0`
2. 检查 Actions 权限设置
3. 手动创建 Release

---

## 性能优化

### 打包优化

减小可执行文件大小:
```python
# 在 pyinstaller.spec 中
a = Analysis(
    # ...
    excludedimports=['tkinter', 'matplotlib'],
    # ...
)
```

### 运行时优化

启用 JIT 编译（可选）:
```bash
pip install numba
```

---

## 定期维护

### 每月检查清单

- [ ] 更新依赖库
- [ ] 运行测试套件
- [ ] 检查安全漏洞
- [ ] 验证文档最新

```bash
# 更新依赖
pip install --upgrade -r requirements.txt

# 检查漏洞
pip install safety
safety check

# 运行测试
pytest tests/ -v
```

### 版本发布前清单

- [ ] 所有测试通过
- [ ] 代码审查完成
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号已更新
- [ ] 本地打包测试成功

---

## 参考资源

- [PyInstaller 文档](https://pyinstaller.readthedocs.io/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [语义版本](https://semver.org/lang/zh-CN/)
- [Keep a Changelog](https://keepachangelog.com/zh-CN/)

---

祝部署顺利! 🚀
