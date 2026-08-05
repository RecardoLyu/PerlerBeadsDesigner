import 'dart:typed_data';

import 'pattern_render.dart';
import 'quantizer.dart';

/// 图纸生成纯 Dart 管线的 isolate 输入（全部字段可跨 isolate 传递：
/// 仅 Uint8List / int / double / bool / String / Palette，无原生句柄）。
class PatternComputeInput {
  final Uint8List imgRgb; // 工作图 RGB（w*h*3）
  final int imgW, imgH;
  final int gw, gh; // 图纸尺寸（豆）
  final int? colorLimit; // null/0 = 不限色
  final double salience;
  final bool dither;
  final double ditherStrength;
  final double icmSmooth; // 0 = 关
  final String metric; // 色差度量（isolate 内设到 palette 上）
  final Palette palette;
  final Uint8List? segMask; // 分割 mask（计算域小图，0/255），无 mask 传 null
  final int segW, segH;

  const PatternComputeInput({
    required this.imgRgb,
    required this.imgW,
    required this.imgH,
    required this.gw,
    required this.gh,
    required this.colorLimit,
    required this.salience,
    required this.dither,
    required this.ditherStrength,
    required this.icmSmooth,
    required this.metric,
    required this.palette,
    required this.segMask,
    required this.segW,
    required this.segH,
  });
}

/// 管线产出（可跨 isolate）。主 isolate 据此喂 ChartPainter.render + 更新状态。
class PatternComputeResult {
  final Uint8List quantRgb; // gw*gh*3 量化后豆图
  final List<String> codes; // gw*gh 逐豆色号
  final List<bool>? beadMask; // 豆网格前景 mask（无 mask 为 null）
  final List<BomEntry> bom;
  final int totalBeads;

  const PatternComputeResult({
    required this.quantRgb,
    required this.codes,
    required this.beadMask,
    required this.bom,
    required this.totalBeads,
  });
}

/// 图纸生成的纯 Dart 计算链（下采样→量化→逐豆色号→mask 对齐→BOM）。
/// 与 PatternNotifier.generate 原主 isolate 内联版本**逐步等价**，只是把
/// 计算整体搬进后台 isolate，让主 isolate 能持续 pump 帧（按钮/颜文字/指示灯即时反馈）。
/// 全部为纯 Dart，不碰 dart:ui / dartcv4 native，可安全 compute()。
///
/// 必须是顶层/静态函数才能作为 compute 的回调。
PatternComputeResult runPatternPipeline(PatternComputeInput inp) {
  // isolate 内把度量设到 palette（Palette.metric 可变）
  inp.palette.metric = inp.metric;

  // 1) 大图 → 豆域小图（盒式平均 = cv2.INTER_AREA，避免高色限摩尔纹）
  final beadRgb = PatternRender.boxAverageDownsample(
      inp.imgRgb, inp.imgW, inp.imgH, inp.gw, inp.gh);

  // 2) 量化（豆域，毫秒级）
  final qres = Quantizer(inp.palette).quantize(
    beadRgb, inp.gh, inp.gw,
    colorLimit:
        (inp.colorLimit == null || inp.colorLimit! <= 0) ? null : inp.colorLimit,
    salience: inp.salience,
    dither: inp.dither,
    ditherStrength: inp.ditherStrength,
    icmSmooth: inp.icmSmooth,
  );

  // 3) 逐豆 code
  final codes = PatternRender.buildCodes(inp.palette, qres.rgb, inp.gw, inp.gh);

  // 4) beadMask：有分割 mask 时对齐到豆网格（对称清写：无 mask 一律 null）
  List<bool>? beadMask;
  if (inp.segMask != null) {
    beadMask = PatternRender.maskToBeadGrid(
        inp.segMask!, inp.segW, inp.segH, inp.gw, inp.gh);
  }

  // 5) BOM（mask 时只计前景）
  final bom = PatternRender.buildBom(
    inp.palette, qres.usage, inp.gw * inp.gh,
    beadMask: beadMask, codes: codes,
  );
  final totalBeads =
      beadMask == null ? inp.gw * inp.gh : beadMask.where((b) => b).length;

  return PatternComputeResult(
    quantRgb: qres.rgb,
    codes: codes,
    beadMask: beadMask,
    bom: bom,
    totalBeads: totalBeads,
  );
}
