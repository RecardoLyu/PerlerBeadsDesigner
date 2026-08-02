import 'package:flutter/material.dart';
import '../../theme/candy_theme.dart';

/// 帮助文档（使用指南）：全屏查看器，从设置页「关于 → 查看使用指南」呼出。
/// 内容面向手机版操作：加载 → 调整 → 分割 → 图纸 → 导出 全流程 + 视图/手势/常见问题。
class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final c = context.candy;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [c.bg, c.bg2],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // 顶栏：返回 + 标题
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 10, 16, 6),
                child: Row(children: [
                  IconButton(
                    icon: Icon(Icons.arrow_back_rounded, color: c.foreground),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                  const SizedBox(width: 4),
                  Text('使用指南',
                      style: TextStyle(fontFamily: 'Fredoka', fontSize: 19, fontWeight: FontWeight.w600, color: c.foregroundStrong)),
                ]),
              ),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
                  children: [
                    _section(c, Icons.rocket_launch_rounded, '快速上手', [
                      _step('1', '在「调整」页点「加载图像」，从相册选一张图。'),
                      _step('2', '（可选）调亮度/对比度/高斯模糊，点「应用调整」叠加效果。'),
                      _step('3', '到「分割」页框选目标，或用「自动分割」一键抠图。'),
                      _step('4', '到「图纸」页设定豆数与颜色参数，点「生成图纸」。'),
                      _step('5', '到「导出」页选分辨率，一键保存 PNG 到相册。'),
                    ]),
                    _section(c, Icons.tune_rounded, '调整', [
                      _p('加载图像后可反复调亮度、对比度、高斯模糊，每次「应用调整」都叠加在当前图上，可连续迭代。'),
                      _p('「恢复原图」一键回到最初加载的图，清除所有调整与分割结果。'),
                    ]),
                    _section(c, Icons.content_cut_rounded, '分割（抠图）', [
                      _p('初始分割：选矩形 / 椭圆 / 自由曲线，在画布上拖出包围目标的区域，松手即自动分割。'),
                      _p('迭代精修：分割不满意时，用红色笔触涂抹「属于目标」的区域、绿色涂抹「不属于目标」的区域，再点「迭代分割」。'),
                      _p('自动分割：不想框选时，从 GrabCut矩形 / 分水岭 / Otsu / SLIC 选一种一键抠图。'),
                      _p('形态学：开运算去毛刺、闭运算补小洞、腐蚀收缩边缘、膨胀扩大边缘；核越大作用越强。'),
                      _p('撤销 / 重做：每步分割、形态学都可撤销，最多回退 8 步。'),
                    ]),
                    _section(c, Icons.grid_on_rounded, '图纸（拼豆图）', [
                      _p('宽度(豆)：图纸横向拼豆数。勾选「保持图像比例」时高度按图像宽高比自动算出并跟随宽度变化。'),
                      _p('颜色上限：限制用几种颜色的豆子；0 = 不限制（最多 221 色 MARD 调色板）。'),
                      _p('细节保留：值越大越保留原图细节，值小则更平滑、用色更省。'),
                      _p('抖动：让颜色过渡更自然；高阶优化(ICM) 进一步减少错色，但更慢。'),
                      _p('使用分割 Mask：勾选后只把分割出的前景生成豆子，背景豆在图纸上淡化显示，BOM 也只计前景豆。'),
                      _p('生成的图纸含网格、坐标刻度与底部 BOM 物料清单（每种颜色豆子的数量）。'),
                    ]),
                    _section(c, Icons.file_download_rounded, '导出', [
                      _p('生成图纸后到「导出」页，选 1080P / 2K / 4K 分辨率，一键把图纸 PNG 保存到相册的「拼豆图纸」文件夹。'),
                    ]),
                    _section(c, Icons.touch_app_rounded, '画布视图与手势', [
                      _p('右上角视图切换：原图 / 高亮 / Mask / 应用结果 / 图纸。分割完成后自动切到 Mask 视图，生成图纸后自动切到图纸视图，可随时手动切回。'),
                      _p('单指拖动：框选或涂抹（取决于当前模式）。'),
                      _p('双指：拖动平移画布、捏合缩放——涂抹精修时也可随时用双指调整视野。'),
                      _p('左侧工具：放大 / 缩小 / 适应窗口。右下角鹰眼缩略图可预览整图。'),
                    ]),
                    _section(c, Icons.palette_rounded, '外观', [
                      _p('「设置 → 外观」可选 跟随系统 / 浅色 / 深色；「跟随系统」随手机系统的深色模式自动切换。'),
                      _p('「设置」里还能配置图纸与分割的默认参数，新建面板时自动带出。'),
                    ]),
                    _section(c, Icons.help_outline_rounded, '常见问题', [
                      _q(c, '形态学提示「已抹去全部前景」？', '当前核太大，把细碎前景抹光了。减小「核大小」再试，或先撤销。'),
                      _q(c, '图纸颜色太杂？', '调低「颜色上限」，或提高「细节保留」让量化更平滑。'),
                      _q(c, '分割把背景也算进去了？', '用绿色笔触涂抹误算的背景区域，再点「迭代分割」精修。'),
                      _q(c, '图纸生成慢？', '大图纸(宽豆多) + 高色限 + ICM 会更慢，属正常；可减小宽度或关闭 ICM。'),
                    ]),
                    const SizedBox(height: 6),
                    Center(
                      child: Text('拼豆图纸生成器 · v2.1.0 移动版',
                          style: TextStyle(fontSize: 11, color: c.mutedFg)),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _section(CandyTheme c, IconData icon, String title, List<Widget> children) {
    return Container(
      margin: const EdgeInsets.only(bottom: 13),
      padding: const EdgeInsets.fromLTRB(15, 12, 15, 14),
      decoration: BoxDecoration(
        color: c.surface,
        border: Border.all(color: c.border),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 15, color: const Color(0xFFE11D48)),
          const SizedBox(width: 7),
          Text(title, style: TextStyle(fontFamily: 'Fredoka', fontSize: 14, fontWeight: FontWeight.w600, color: c.foregroundStrong)),
        ]),
        const SizedBox(height: 8),
        ...children,
      ]),
    );
  }

  Widget _p(String text) => Builder(
        builder: (ctx) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Text(text, style: TextStyle(fontSize: 12.5, height: 1.5, color: ctx.candy.foreground)),
        ),
      );

  Widget _step(String n, String text) => Builder(
        builder: (ctx) {
          final c = ctx.candy;
          return Padding(
            padding: const EdgeInsets.only(bottom: 7),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                width: 19, height: 19,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [Color(0xFFA78BFA), Color(0xFF7C3AED)]),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(n, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: Colors.white)),
              ),
              const SizedBox(width: 9),
              Expanded(child: Text(text, style: TextStyle(fontSize: 12.5, height: 1.45, color: c.foreground))),
            ]),
          );
        },
      );

  Widget _q(CandyTheme c, String q, String a) => Builder(
        builder: (ctx) {
          final cc = ctx.candy;
          return Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Q  $q', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: cc.foregroundStrong)),
              const SizedBox(height: 2),
              Text('A  $a', style: TextStyle(fontSize: 12, height: 1.45, color: cc.foreground)),
            ]),
          );
        },
      );
}
