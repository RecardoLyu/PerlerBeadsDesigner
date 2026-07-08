# 变更日志 (CHANGELOG)

所有项目的重要变化都记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 标准。

## [1.0.0] - 2024-02-10

### 初始发布

#### 新增功能

- 图像加载和基本处理
  - 支持 JPG、PNG、BMP 等常见格式
  - 图像调整大小
  - 亮度和对比度调整
  - 灰度转换

- 前景分割和裁剪
  - GrabCut 算法分割
  - 自适应阈值处理
  - 简单阈值处理
  - 颜色范围选择
  - 形态学操作（开运算、闭运算）
  - 鼠标矩形选区裁剪

- 颜色管理
  - 从 Pixel Beads 网站自动获取实时颜色库
  - 颜色匹配和量化
  - 调色板管理
  - 颜色编码（如 A1、B2）

- 图案生成
  - 自动将图像转换为拼豆图案
  - 可自定义拼豆数量
  - 颜色数量限制选项

- 渲染选项
  - 带网格的渲染
  - 带颜色代码的渲染
  - 自定义显示尺寸

- 导出功能
  - PNG 导出（带编码、带网格）
  - PDF 导出（含物料清单）
  - BOM 导出（JSON 和 CSV 格式）

- 用户界面
  - PyQt6 图形界面
  - 标签页设计，功能模块化
  - 实时预览
  - 拖拽支持

#### 技术细节
- 核心模块：图像处理、颜色管理、图案生成
- 前景分割算法：GrabCut、自适应阈值等
- 导出引擎：PNG/PDF 生成
- 网络爬虫：自动获取颜色库

#### 文档
- 详细的 README 和快速入门指南
- 开发指南
- API 文档
- 代码示例

#### 项目设置
- Python 3.8+ 支持
- 虚拟环境配置
- PyInstaller 打包配置
- GitHub Actions 自动构建
- VS Code 调试配置

---

## 版本方案

本项目采用 [语义版本](https://semver.org/lang/zh-CN/) 控制：

- **主版本号（MAJOR）**：不兼容的 API 修改时增加
- **次版本号（MINOR）**：以向下兼容的方式增加功能时增加
- **修订号（PATCH）**：进行向下兼容的缺陷修正时增加

## 如何升级

### 从源代码安装（开发版本）
```bash
git clone https://github.com/yourusername/PerlerBeadsDesigner.git
cd PerlerBeadsDesigner
pip install -r requirements.txt
python -m src.main
```

### 使用可执行文件
从 [Releases](https://github.com/yourusername/PerlerBeadsDesigner/releases) 页面下载最新版本。

## 计划中的功能

以下功能可能在未来版本中添加：

- [ ] 实时预览优化
- [ ] 更多分割算法
- [ ] 支持更多输出格式（TIFF、SVG）
- [ ] 图案合并和平铺
- [ ] 批量处理
- [ ] 插件系统
- [ ] 国际化（多语言支持）
- [ ] 移动端应用
- [ ] Web 版本

## 问题和反馈

如遇到问题或有功能建议，请在 GitHub Issues 中提报。

---

最后更新：2024-02-10
