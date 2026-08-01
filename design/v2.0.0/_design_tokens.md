# PerlerBeadsDesigner v2.0.0 设计系统 Token（玻璃拟态 · 糖果系 · 亮/暗双主题）

> 所有设计稿（HTML 高保真）**必须严格遵守**本文件的设计 token。这是统一基调，由 ui-ux-pro-max 方法论生成并经项目确认。

## 一、产品语境
- **产品**：拼豆图纸设计器（图像 → 拼豆图纸 + BOM），桌面应用。
- **用户**：年轻群体；行业：文化创意 + 情绪消费（手工 DIY、解压、治愈）。
- **气质**：整体简约、明亮活泼、糖果系、治愈、有温度；玻璃拟态（glassmorphism）为标志性视觉；动画流畅迅速。

## 二、字体
```css
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@300;400;500;600;700;800&display=swap');
```
- 标题 / 品牌：`font-family: 'Fredoka', sans-serif;`
- 正文 / UI：`font-family: 'Nunito', sans-serif;`
- 中文回退：`"PingFang SC","Microsoft YaHei",sans-serif`

## 三、色板（CSS 变量；亮/暗两套）
用 `:root` 与 `[data-theme="dark"]` 定义，切换 `data-theme` 即换主题。**禁止在组件里写死裸 hex，一律用变量。**

### 亮色（默认 `:root`）
```css
:root{
  --color-primary:#E11D48;      /* 活力玫瑰主色 */
  --color-on-primary:#FFFFFF;
  --color-secondary:#FB7185;    /* 糖果粉 */
  --color-accent:#2563EB;       /* 点缀蓝（CTA/强调） */
  --color-on-accent:#FFFFFF;
  --color-violet:#A78BFA;       /* 渐变辅助紫 */
  --color-violet-deep:#7C3AED;
  --color-bg:#FFF1F2;           /* 浅粉底 */
  --color-bg-2:#FFE4E6;
  --color-surface:rgba(255,255,255,.55);   /* 玻璃卡片底 */
  --color-surface-strong:rgba(255,255,255,.75);
  --color-foreground:#4A1428;   /* 主文字（深玫瑰棕） */
  --color-foreground-strong:#881337;
  --color-muted:#F0ECF2;
  --color-muted-fg:#9A6B7C;
  --color-border:rgba(225,29,72,.18);
  --color-destructive:#DC2626;
  --color-ring:#E11D48;
  --glass-blur:18px;
}
```

### 暗色（`[data-theme="dark"]`）
```css
[data-theme="dark"]{
  --color-primary:#FB7185;      /* 提亮保证对比 */
  --color-on-primary:#2A0A12;
  --color-secondary:#FDA4AF;
  --color-accent:#60A5FA;
  --color-on-accent:#0B1220;
  --color-violet:#C4B5FD;
  --color-violet-deep:#A78BFA;
  --color-bg:#1A0F14;           /* 深墨玫瑰底 */
  --color-bg-2:#241019;
  --color-surface:rgba(46,22,32,.45);
  --color-surface-strong:rgba(58,28,40,.6);
  --color-foreground:#F6E4EA;
  --color-foreground-strong:#FBD5DE;
  --color-muted:#2E1620;
  --color-muted-fg:#B98A99;
  --color-border:rgba(251,113,133,.22);
  --color-destructive:#F87171;
  --color-ring:#FB7185;
}
```

## 四、玻璃拟态卡片（标志性组件）
```css
.glass{
  background:var(--color-surface);
  backdrop-filter:blur(var(--glass-blur)) saturate(160%);
  -webkit-backdrop-filter:blur(var(--glass-blur)) saturate(160%);
  border:1px solid var(--color-border);
  border-radius:24px;
  box-shadow:0 8px 32px rgba(136,19,55,.12), inset 0 1px 0 rgba(255,255,255,.35);
}
```
- 背景要有「内容可透出」才看得出玻璃感：App 背景用柔和渐变 + 缓动漂浮的彩色 blob（粉/紫/橙），玻璃卡片叠其上。
- 暗色下 `box-shadow` 改用更淡的内发光。

## 五、圆角
- 大容器/主面板：32-40px
- 卡片 `.glass`：24px
- 按钮：16-20px（胶囊形可 999px）
- 输入/下拉：12-14px
- 小徽章/BOM 芯片：999px（全圆角）

## 六、按钮
- 主按钮：渐变 `linear-gradient(135deg,var(--color-violet),var(--color-violet-deep))` 或主色实底，白字，圆角 16px，按下 `transform:scale(.96)` 弹性。
- 次按钮：`.glass` 玻璃底 + 主色描边/文字。
- 危险按钮：`--color-destructive`。
- 所有可点元素 `cursor:pointer`，hover 150-300ms 过渡。

## 七、间距（density 5/10 标准）
基础 8px 网格：`--space-1:8px --space-2:16px --space-3:24px --space-4:32px --space-6:48px`。控件间 12-16px，卡片内边距 20-24px。

## 八、动效（motion 6/10 标准，流畅迅速）
- 通用过渡：`transition:all .25s cubic-bezier(.34,1.56,.64,1)`（带回弹）。
- 主题切换：所有涉及颜色的属性 `transition:background-color .3s,color .3s,border-color .3s`，平滑无跳变。
- 列表/卡片入场： stagger `opacity 0→1, translateY 16→0, scale .94→1`，`back.out(1.4)`。
- 面板/视图切换：快速 fade+slide，200-300ms。
- 尊重 `prefers-reduced-motion`：关闭非必要动画。
- 按下反馈：scale .95-.96 弹性回弹。

## 九、背景漂浮 blob（玻璃拟态的「背后内容」）
```css
.blob{position:fixed;border-radius:50%;filter:blur(70px);opacity:.5;pointer-events:none;z-index:0;}
/* 粉 #FB7185 / 紫 #A78BFA / 橙 #FDBA74 三团，缓慢 ±20px 漂移，暗色下 opacity .3 */
```

## 十、布局骨架（桌面，左右分栏，参考现有功能）
- 顶部：左侧品牌 + 玻璃搜索/状态，右侧 **亮/暗主题切换**（太阳/月亮 SVG 图标，不用 emoji）、帮助按钮。
- 左侧：可收缩导航/参数面板（玻璃卡片堆叠，圆角）。
- 右侧主区：图像/图纸预览画布（大玻璃卡片，内嵌图像显示，支持缩放/平移/鹰眼占位）。
- 状态栏：左下角忙碌指示（计算中…动画）、状态文本。
- 顶部主导航：「图像处理」「图纸生成」两个主视图切换（对应现有两大 tab）。

## 十一、硬规则（ui-ux-pro-max 交付前检查）
- ❌ 不用 emoji 当图标，一律内联 SVG（Lucide/Heroicons 风格线性图标）。
- ✅ 文本对比度：亮色正文 ≥4.5:1；暗色注意提亮。
- ✅ 可点元素 cursor-pointer + hover 过渡 150-300ms。
- ✅ 键盘 focus 可见（`outline:2px solid var(--color-ring)`）。
- ✅ 尊重 prefers-reduced-motion。

## 十二、功能接口映射（供设计稿占位，来自现有 Tkinter 版）
设计稿需为这些功能留出 UI 位置（可用占位/mock 数据）：
- **图像处理**：加载图像、亮度/对比度滑条、高斯模糊（核大小+自动建议+应用）、裁剪（启用/应用/取消）、旋转（↺90/↻90/180/任意角）、水平/垂直翻转、恢复原图。
- **分割**：迭代 GrabCut（形状选择 矩形/椭圆/自由曲线、1.绘制前景区域 2.第一次分割 3.迭代分割、前景(红)/背景(绿)标注、笔触粗细滑块+圆形预览、清除标注、应用分割结果）；自动分割（方法下拉 GrabCut/分水岭/Otsu/SLIC + 按方法参数 + 执行分割 + 应用分割结果）；形态学（核大小、结构元素形状、开/闭/腐蚀/膨胀）。
- **显示切换**：原图 / 原图+高亮 / Mask / Mask应用结果（下拉）。
- **图纸生成**：高/宽 Spinbox（默认 52，保持比例联动）、颜色数量限制、色彩空间度量、细节保留、抖动开关+强度、ICM 高阶优化开关+强度、使用 Mask 结果、生成图纸。
- **导出**：导出预览（网格预览/标准图纸切换）、文件名、PNG 缩放倍数、PDF 纸张 A4/Letter、导出 PNG/导出 PDF 复选、一键导出、选择输出路径。
- **BOM 物料清单**：颜色芯片列表（色块+色号+数量，按用量排序）。
- **图像画布交互**：缩放（Ctrl+滚轮/按钮）、中键平移、鹰眼 minimap、裁剪框选、GrabCut 圈选/涂抹。
