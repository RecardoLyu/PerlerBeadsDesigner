import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:opencv_dart/opencv_dart.dart' as cv;
import '../algo/basic_adjust.dart';
import '../algo/cv_ops.dart';
import '../algo/pattern_render.dart';
import '../algo/quantizer.dart';
import '../algo/slic.dart';
import '../ui/canvas/chart_painter.dart';

/// 主题模式（亮/暗/跟随系统）。
class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier() : super(ThemeMode.system);
  void set(ThemeMode m) => state = m;
  /// 顶栏快捷切换：亮 ↔ 暗（跟随系统需到设置里选）。
  void toggle() => state = state == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
}

final themeModeProvider =
    StateNotifierProvider<ThemeModeNotifier, ThemeMode>((_) => ThemeModeNotifier());

/// 应用设置：算法默认参数。各面板初始值从这里取。
class AppSettings {
  final int defWidth; // 图纸宽（豆）
  final bool keepRatio; // 保持图像比例
  final int maxColors; // 颜色上限（0=不限）
  final double salience; // 细节保留
  final String metric; // 颜色度量
  final bool dither; // 抖动
  final double ditherStrength;
  final bool icm; // 高阶优化
  final double icmSmooth;
  final double brushSize; // 迭代分割笔触粗细（直径 px）
  final String segMethod; // 自动分割默认方法
  const AppSettings({
    this.defWidth = 104,
    this.keepRatio = true,
    this.maxColors = 0,
    this.salience = 1.0,
    this.metric = 'ciede2000',
    this.dither = false,
    this.ditherStrength = 1.0,
    this.icm = false,
    this.icmSmooth = 0.5,
    this.brushSize = 12,
    this.segMethod = 'watershed',
  });

  AppSettings copyWith({
    int? defWidth, bool? keepRatio, int? maxColors, double? salience,
    String? metric, bool? dither, double? ditherStrength, bool? icm,
    double? icmSmooth, double? brushSize, String? segMethod,
  }) =>
      AppSettings(
        defWidth: defWidth ?? this.defWidth,
        keepRatio: keepRatio ?? this.keepRatio,
        maxColors: maxColors ?? this.maxColors,
        salience: salience ?? this.salience,
        metric: metric ?? this.metric,
        dither: dither ?? this.dither,
        ditherStrength: ditherStrength ?? this.ditherStrength,
        icm: icm ?? this.icm,
        icmSmooth: icmSmooth ?? this.icmSmooth,
        brushSize: brushSize ?? this.brushSize,
        segMethod: segMethod ?? this.segMethod,
      );
}

final settingsProvider = StateProvider<AppSettings>((_) => const AppSettings());

/// 状态行文案
final statusMessageProvider = StateProvider<String>((_) => '就绪');

/// 全局忙碌状态（任何长任务都算：图像加载/调整 + 分割/形态学）。
/// 用于状态行右侧的颜文字 + 跳动省略号指示（对应桌面版 busy 状态栏）。
class BusyNotifier extends StateNotifier<bool> {
  BusyNotifier(this._ref) : super(false);
  final Ref _ref;
  void refresh() {
    final b = _ref.read(imageProvider).busy ||
        _ref.read(segmentProvider).busy ||
        _ref.read(patternProvider).busy;
    if (b != state) state = b;
  }
}

final busyProvider = StateNotifierProvider<BusyNotifier, bool>((ref) => BusyNotifier(ref));

/// 当前画布视图模式：原图 / 高亮 / Mask / 应用结果 / 图纸
enum CanvasViewMode { original, highlight, mask, applied, pattern }

final viewModeProvider = StateProvider<CanvasViewMode>((_) => CanvasViewMode.original);

/// 画布交互模式：浏览（缩放平移）/ 框选（GrabCut ROI）/ 涂抹（前景/背景修正）/ 裁剪。
enum CanvasInteraction { pan, selectRect, selectEllipse, selectFree, scribbleFg, scribbleBg, crop }

final interactionProvider =
    StateProvider<CanvasInteraction>((_) => CanvasInteraction.pan);

/// 请求进入某种交互模式的信号（面板点「开始框选/涂抹」时 +1）。
/// 画布在渲染前同步消费它并切 interaction，避免「点了第一次没生效、要框两次」。
final interactionRequestProvider = StateProvider<CanvasInteraction>((_) => CanvasInteraction.pan);

/// 当前编辑中的裁剪框（图像像素坐标 Rect；null=未框选）。裁剪模式下由画布维护，
/// 面板「应用裁剪」读取它。图像像素坐标保证缩放/旋转时框不漂移。
final cropRectProvider = StateProvider<Rect?>((_) => null);

/// 拼豆品牌颜色库（与桌面端 ColorManager.BRANDS 对齐）。切换后图纸失效需重新生成。
final brandProvider = StateProvider<String>((_) => 'mard');

/// 源图片文件名（去扩展名），图纸顶部标题用。占位名（图像/未命名/image/空）→ null 不渲染。
final sourceNameProvider = StateProvider<String?>((_) => null);

/// 是否在图纸顶部渲染文件名标题（默认不渲染，由导出页复选框控制）。
final showChartTitleProvider = StateProvider<bool>((_) => false);

/// 导出页文件名输入框当前值（图纸标题来源；默认跟随源图）。
final exportNameProvider = StateProvider<String>((_) => 'pattern');

/// 由文件名推标题：去路径去扩展名，占位名返回 null。
String? deriveSourceTitle(String filename) {
  var base = filename.split(RegExp(r'[\\/]')).last;
  final dot = base.lastIndexOf('.');
  if (dot > 0) base = base.substring(0, dot);
  base = base.trim();
  const placeholders = {'', 'image', 'untitled', '未命名', '图像', '未命名图纸'};
  return placeholders.contains(base.toLowerCase()) ? null : base;
}

/// 取消一切画布子交互（框选/涂抹/裁剪），回到浏览态。
/// 进入任何新交互（点其他分割方法、点裁剪、切 Tab）前调用，防止上一个交互泄露。
/// 参数用 WidgetRef（面板/Sheet 内的 ref）；WidgetRef 与 Ref 都暴露 .read。
void cancelCanvasInteraction(WidgetRef ref) {
  ref.read(cropRectProvider.notifier).state = null;
  ref.read(interactionRequestProvider.notifier).state = CanvasInteraction.pan;
  ref.read(interactionProvider.notifier).state = CanvasInteraction.pan;
}

/// GrabCut 框选形状（矩形/椭圆/自由曲线）。
enum SelectShape { rect, ellipse, free }

/// 图纸目标尺寸（豆）。分割下采样目标分辨率据此计算（4× 图纸宽），
/// M3 由图纸面板写入。保持图像比例时高=宽。默认 104 豆（→ 下采样到 416px）。
final patternGridProvider = StateProvider<(int, int)>((_) => (104, 104));

/// 一幅 RGB 图像：字节 + 尺寸 + 解码后的 ui.Image（供画布显示）。
/// [rgbaBytes] 为 h*w*4 的 RGBA（ui.Image 用），[rgbBytes] 为 h*w*3 的 RGB（OpenCV 用）。
class WorkingImage {
  final int width;
  final int height;
  final Uint8List rgbBytes; // h*w*3，OpenCV 输入
  final ui.Image uiImage; // 画布显示
  const WorkingImage({
    required this.width,
    required this.height,
    required this.rgbBytes,
    required this.uiImage,
  });
}

/// 把 RGB(h*w*3) 字节转成 ui.Image（RGBA 内部表示）。
Future<ui.Image> rgbToUiImage(Uint8List rgb, int w, int h) async {
  final rgba = Uint8List(w * h * 4);
  for (var i = 0, j = 0; i < w * h * 3; i += 3, j += 4) {
    rgba[j] = rgb[i];
    rgba[j + 1] = rgb[i + 1];
    rgba[j + 2] = rgb[i + 2];
    rgba[j + 3] = 255;
  }
  final comp = Completer<ui.Image>();
  ui.decodeImageFromPixels(
    rgba,
    w,
    h,
    ui.PixelFormat.rgba8888,
    (img) => comp.complete(img),
  );
  return comp.future;
}

/// 把 RGBA(h*w*4) 字节转成 ui.Image。
Future<ui.Image> rgbaToUiImage(Uint8List rgba, int w, int h) async {
  final comp = Completer<ui.Image>();
  ui.decodeImageFromPixels(rgba, w, h, ui.PixelFormat.rgba8888, (img) => comp.complete(img));
  return comp.future;
}

/// 把 RGB 原图 + 0/255 掩码按视图模式离线合成为一张 RGBA 图（一次性，供画布直接显示）。
/// 这是掩码显示的正确做法：合成一次缓存成 ui.Image，画布显示它和显示原图一样便宜，
/// 绝不逐像素 drawRect（那对手机是几百万次/帧的灾难）。
Uint8List compositeMask(Uint8List rgb, Uint8List mask, int w, int h, CanvasViewMode mode) {
  final rgba = Uint8List(w * h * 4);
  for (var i = 0, j = 0; i < w * h; i++, j += 4) {
    final r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
    final fg = mask[i] > 0;
    switch (mode) {
      case CanvasViewMode.mask:
        // 前景白、背景深灰
        if (fg) { rgba[j] = 255; rgba[j+1] = 255; rgba[j+2] = 255; }
        else { rgba[j] = 30; rgba[j+1] = 30; rgba[j+2] = 30; }
        break;
      case CanvasViewMode.highlight:
        // 前景原色，背景压暗
        if (fg) { rgba[j] = r; rgba[j+1] = g; rgba[j+2] = b; }
        else {
          rgba[j] = (r * 0.3).round(); rgba[j+1] = (g * 0.3).round(); rgba[j+2] = (b * 0.3).round();
        }
        break;
      case CanvasViewMode.applied:
        // 前景原色，背景去色（转灰再提亮）
        if (fg) { rgba[j] = r; rgba[j+1] = g; rgba[j+2] = b; }
        else {
          final gray = ((r * 299 + g * 587 + b * 114) ~/ 1000);
          final v = (gray * 0.4 + 255 * 0.6).round();
          rgba[j] = v; rgba[j+1] = v; rgba[j+2] = v;
        }
        break;
      case CanvasViewMode.original:
      case CanvasViewMode.pattern:
        // pattern 实际不走 composite（走 chartImage），这里给编译穷举一个安全兜底（原色）。
        rgba[j] = r; rgba[j+1] = g; rgba[j+2] = b;
    }
    rgba[j + 3] = 255;
  }
  return rgba;
}

/// 异步分块版 compositeMask：按行块处理，每块结束 `await` 让出事件循环一次。
/// 大图（原图分辨率，百万像素级）逐像素合成是最重的一帧，会占满主 isolate 阻塞
/// 状态行颜文字动画。分块让出让动画帧得以插入，颜文字在计算中也能持续跳动。
/// 仅 _rebuildComposite 用；其它小图场景仍用同步 compositeMask。
Future<Uint8List> compositeMaskAsync(Uint8List rgb, Uint8List mask, int w, int h, CanvasViewMode mode) async {
  final rgba = Uint8List(w * h * 4);
  const rowsPerChunk = 64; // 每 64 行让出一次事件循环
  for (var y0 = 0; y0 < h; y0 += rowsPerChunk) {
    final yEnd = (y0 + rowsPerChunk) < h ? (y0 + rowsPerChunk) : h;
    for (var y = y0; y < yEnd; y++) {
      final rowBase = y * w;
      for (var x = 0; x < w; x++) {
        final i = rowBase + x, j = i * 4;
        final r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
        final fg = mask[i] > 0;
        switch (mode) {
          case CanvasViewMode.mask:
            if (fg) { rgba[j] = 255; rgba[j+1] = 255; rgba[j+2] = 255; }
            else { rgba[j] = 30; rgba[j+1] = 30; rgba[j+2] = 30; }
          case CanvasViewMode.highlight:
            if (fg) { rgba[j] = r; rgba[j+1] = g; rgba[j+2] = b; }
            else {
              rgba[j] = (r * 0.3).round(); rgba[j+1] = (g * 0.3).round(); rgba[j+2] = (b * 0.3).round();
            }
          case CanvasViewMode.applied:
            if (fg) { rgba[j] = r; rgba[j+1] = g; rgba[j+2] = b; }
            else {
              final gray = ((r * 299 + g * 587 + b * 114) ~/ 1000);
              final v = (gray * 0.4 + 255 * 0.6).round();
              rgba[j] = v; rgba[j+1] = v; rgba[j+2] = v;
            }
          case CanvasViewMode.original:
          case CanvasViewMode.pattern:
            rgba[j] = r; rgba[j+1] = g; rgba[j+2] = b;
        }
        rgba[j + 3] = 255;
      }
    }
    // 让出事件循环，给动画/手势/重绘一次运行机会
    await Future.delayed(Duration.zero);
  }
  return rgba;
}

/// 图像处理状态：源图（加载时的原图）+ 工作图（应用调整后的当前图）。
class ImageState {
  final WorkingImage? source; // 原图，「恢复原图」用
  final WorkingImage? working; // 当前显示/处理图
  final bool busy; // 是否正在处理（加载/应用中）
  const ImageState({this.source, this.working, this.busy = false});

  bool get hasImage => working != null;

  ImageState copyWith({
    WorkingImage? source,
    WorkingImage? working,
    bool? busy,
  }) =>
      ImageState(
        source: source ?? this.source,
        working: working ?? this.working,
        busy: busy ?? this.busy,
      );
}

// ---- isolate 说明：opencv_dart(dartcv4) 的 native 绑定不能跨 isolate 调用，
// 故所有 OpenCV 运算均在主 isolate 直接执行（手机端通常 <1s，配合 busy 遮罩）。
// 纯 Dart 算法（SLIC/量化等）如需 isolate 可另行用 compute（不触碰 native）。

class ImageNotifier extends StateNotifier<ImageState> {
  ImageNotifier(this._ref) : super(const ImageState());
  final Ref _ref;

  void _status(String m) => _ref.read(statusMessageProvider.notifier).state = m;

  /// 加载图像（从 RGB 字节，解码显示 + 存源图）。
  /// 调用方负责从 image_picker/file_picker 读文件并解码为 RGB。
  Future<void> loadFromRgb(Uint8List rgb, int w, int h, {String name = '图像'}) async {
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在解码 $name …');
    try {
      final uiImg = await rgbToUiImage(rgb, w, h);
      final wi = WorkingImage(width: w, height: h, rgbBytes: rgb, uiImage: uiImg);
      state = ImageState(source: wi, working: wi, busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _ref.read(sourceNameProvider.notifier).state = deriveSourceTitle(name);
      // 导出文件名跟随源图（占位名回退 pattern）
      _ref.read(exportNameProvider.notifier).state =
          deriveSourceTitle(name) ?? 'pattern';
      _ref.read(segmentProvider.notifier).reset();
      _ref.read(patternProvider.notifier).reset();
      _status('已加载 $name（$w×$h）');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('加载失败：$e');
    }
  }

  /// 应用基本调整：亮度/对比度 + 高斯模糊，叠加在当前工作图上。
  Future<void> applyAdjust({
    required double brightness,
    required double contrast,
    required int blurKsize,
  }) async {
    final cur = state.working;
    if (cur == null) {
      _status('请先加载图像');
      return;
    }
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在应用调整…');
    try {
      var rgb = cur.rgbBytes;
      final w = cur.width, h = cur.height;
      // 亮度/对比度 + 高斯模糊：纯 Dart 实现（image 包），不触 OpenCV native。
      if ((brightness - 1.0).abs() > 1e-6 || (contrast - 1.0).abs() > 1e-6) {
        rgb = BasicAdjust.brightnessContrast(rgb, w, h, brightness, contrast);
      }
      // 高斯核大小(1-15) → 模糊半径；ksize=1 不模糊
      if (blurKsize > 1) {
        final radius = ((blurKsize - 1) / 2).round().clamp(1, 25);
        rgb = BasicAdjust.gaussianBlur(rgb, w, h, radius);
      }
      final uiImg = await rgbToUiImage(rgb, w, h);
      final wi = WorkingImage(width: w, height: h, rgbBytes: rgb, uiImage: uiImg);
      state = state.copyWith(working: wi, busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _ref.read(segmentProvider.notifier).reset();
      _ref.read(patternProvider.notifier).reset();
      _status('已应用调整');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('调整失败：$e');
    }
  }

  /// 恢复原图：工作图回退到源图。
  void restoreSource() {
    final src = state.source;
    if (src == null) {
      _status('请先加载图像');
      return;
    }
    state = state.copyWith(working: src);
    _ref.read(segmentProvider.notifier).reset();
    _ref.read(patternProvider.notifier).reset();
    _status('已恢复原图');
  }

  /// 应用裁剪：把 working 裁成矩形区域，并把结果同时设为新的 source（新「原图」）。
  /// 这样「恢复原图」只回到裁剪后状态，不会回到裁剪前；重新导入才会彻底重置。
  /// 基于 working（含已应用的亮度/对比度调整），所见即所裁。
  Future<void> applyCrop(Rect rect) async {
    final cur = state.working;
    if (cur == null) {
      _status('请先加载图像');
      return;
    }
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在裁剪…');
    try {
      final x = rect.left.round(), y = rect.top.round();
      final cw = rect.width.round(), ch = rect.height.round();
      if (cw < 2 || ch < 2) {
        state = state.copyWith(busy: false);
        _ref.read(busyProvider.notifier).refresh();
        _status('裁剪区域太小');
        return;
      }
      final cropped = BasicAdjust.cropRgb(cur.rgbBytes, cur.width, cur.height, x, y, cw, ch);
      // cropRgb 内部已 clamp，实际尺寸可能略小于请求，需重算
      final rw = cw.clamp(1, cur.width - x.clamp(0, cur.width));
      final rh = ch.clamp(1, cur.height - y.clamp(0, cur.height));
      final uiImg = await rgbToUiImage(cropped, rw, rh);
      final wi = WorkingImage(width: rw, height: rh, rgbBytes: cropped, uiImage: uiImg);
      // 关键：source 与 working 同时指向裁剪结果 → 裁剪成新原图
      state = ImageState(source: wi, working: wi, busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _ref.read(segmentProvider.notifier).reset();
      _ref.read(patternProvider.notifier).reset();
      _ref.read(cropRectProvider.notifier).state = null;
      _status('已裁剪（$rw×$rh），成为新原图');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('裁剪失败：$e');
    }
  }

  /// 清除图像（回到空态）。
  void clear() {
    state = const ImageState();
    _status('就绪');
  }
}

final imageProvider =
    StateNotifierProvider<ImageNotifier, ImageState>((ref) => ImageNotifier(ref));

// ======================= 分割（M2） =======================

/// 分割状态：当前 mask + GrabCut session + 撤销/重做栈。
/// mask 为 _workW*_workH（计算域小图尺寸）的 0/255 字节（前景=255）。
class SegmentState {
  final Uint8List? mask; // 当前二值 mask（计算域小图）
  final int width;  // mask 宽（= _workW）
  final int height; // mask 高（= _workH）
  final bool busy;
  final bool hasGrabCutSession; // 是否已有 GrabCut 初始结果（可迭代）
  final int undoCount;
  final int redoCount;
  final ui.Image? composite; // 合成显示图（计算域小图，画布直接显示）
  final int compositeVersion; // 每次重建 +1，画布据此刷新
  final Uint8List? fgDisplay; // 前景涂抹显示缓冲（计算域小图 0/255，供叠层画点）
  final Uint8List? bgDisplay; // 背景涂抹显示缓冲
  final int scribbleVersion; // 涂抹显示缓冲变化 +1，叠层据此重绘
  final double brushRadius; // 当前笔触半径（原图像素），叠层据此调点大小
  const SegmentState({
    this.mask,
    this.width = 0,
    this.height = 0,
    this.busy = false,
    this.hasGrabCutSession = false,
    this.undoCount = 0,
    this.redoCount = 0,
    this.composite,
    this.compositeVersion = 0,
    this.fgDisplay,
    this.bgDisplay,
    this.scribbleVersion = 0,
    this.brushRadius = 6.0,
  });

  bool get hasMask => mask != null;

  SegmentState copyWith({
    Uint8List? mask,
    int? width,
    int? height,
    bool? busy,
    bool? hasGrabCutSession,
    int? undoCount,
    int? redoCount,
    ui.Image? composite,
    int? compositeVersion,
    Uint8List? fgDisplay,
    Uint8List? bgDisplay,
    int? scribbleVersion,
    double? brushRadius,
    bool clearMask = false,
    bool clearComposite = false,
    bool clearScribbleDisplay = false,
  }) =>
      SegmentState(
        mask: clearMask ? null : (mask ?? this.mask),
        width: width ?? this.width,
        height: height ?? this.height,
        busy: busy ?? this.busy,
        hasGrabCutSession: hasGrabCutSession ?? this.hasGrabCutSession,
        undoCount: undoCount ?? this.undoCount,
        redoCount: redoCount ?? this.redoCount,
        composite: clearComposite ? null : (composite ?? this.composite),
        compositeVersion: compositeVersion ?? this.compositeVersion,
        fgDisplay: clearScribbleDisplay ? null : (fgDisplay ?? this.fgDisplay),
        bgDisplay: clearScribbleDisplay ? null : (bgDisplay ?? this.bgDisplay),
        scribbleVersion: scribbleVersion ?? this.scribbleVersion,
        brushRadius: brushRadius ?? this.brushRadius,
      );
}

/// 分割引擎：GrabCut session + 自动分割 + 形态学 + 撤销/重做。
/// 对应桌面版 IterativeGrabCutState + ImageSegmentation。
/// 所有 OpenCV 运算在主 isolate 直接执行（dartcv4 native 不可跨 isolate）。
class SegmentNotifier extends StateNotifier<SegmentState> {
  SegmentNotifier(this._ref) : super(const SegmentState());
  final Ref _ref;

  // GrabCut session（dartcv4 对象，不能进 state）
  cv.Mat? _bgdModel;
  cv.Mat? _fgdModel;
  Uint8List? _gcMask; // 当前 GrabCut 二值结果（0/255）

  // 合成重建令牌：快速连切视图时多个 _rebuildComposite 并发 await 解码，
  // 后到者若落在先完成者之后会用过期模式覆盖 composite、并 dispose 掉画布正在显示的图
  // → 「视图反复切换导致 mask 失效/闪回原图」。令牌单调递增，await 后若已过期则丢弃
  // 自己解码的图（dispose 之），只让最后一次重建生效。
  int _compositeToken = 0;

  /// 分割完成后重建合成显示图（当前 viewMode），存入 state.composite。
  /// 在状态层离线合成一次，画布直接显示这张 ui.Image，零逐像素计算。
  /// 合成在**原图分辨率**上进行（mask 从计算域小图放大回原图，用原图 rgbBytes），
  /// 保证显示锐利、不糊、尺寸不跳变 —— 只有 CV 计算用压缩小图。
  Future<void> _rebuildComposite({bool switchToMask = false}) async {
    final token = ++_compositeToken;
    final m = state.mask;
    final img = _img;
    if (m == null || img == null || !_ensureWork() || _workRgb == null) {
      state = state.copyWith(clearComposite: true);
      return;
    }
    // switchToMask（分割完成）时目标视图是高亮：直接用高亮模式合成，
    // 保证切过去显示的正是高亮图（否则会用切换前的旧模式合成，切过去内容不符）。
    final mode = switchToMask ? CanvasViewMode.highlight : _ref.read(viewModeProvider);
    final dw = img.width, dh = img.height;
    // mask 是计算域小图（_workW×_workH），先放大回原图尺寸（nearest 保二值边缘）
    final bigMask = (dw == _workW && dh == _workH)
        ? m
        : BasicAdjust.resizeMask(m, _workW, _workH, dw, dh);
    // 用原图合成 → 显示清晰（分块异步让出事件循环，避免阻塞颜文字动画）
    final rgba = await compositeMaskAsync(img.rgbBytes, bigMask, dw, dh, mode);
    // await 期间又有更新的重建进来（连切视图）→ 丢弃这次，不动 state。
    if (token != _compositeToken) {
      return;
    }
    final uiImg = await rgbaToUiImage(rgba, dw, dh);
    // 再次检查令牌（rgbaToUiImage 也是 await）
    if (token != _compositeToken) {
      uiImg.dispose();
      return;
    }
    state.composite?.dispose();
    state = state.copyWith(
      composite: uiImg,
      compositeVersion: state.compositeVersion + 1,
    );
    // 分割完成（非视图切换触发的重建）→ composite 就绪后才切到高亮视图，
    // 保证画布立刻有图可显示，不会切过去还是原图。
    // 默认高亮（前景原色+背景压暗）：比纯 Mask 更直观地看到抠出的目标长什么样，
    // 也便于直接在上面涂抹精修（涂抹本就默认在高亮画布上进行）。
    if (switchToMask) {
      _ref.read(viewModeProvider.notifier).state = CanvasViewMode.highlight;
    }
  }

  /// 切换视图模式时按当前模式重建合成（供画布调用；不触发再次切视图）。
  /// 防御：只在「确有 mask」时重建；无 mask（或工作图未就绪）保持现有 composite，
  /// 避免竞态/时序把 composite 清成 null → 之后 mask/高亮/应用结果全显示原图、看似 mask 失效。
  Future<void> refreshComposite() {
    if (state.mask == null) return Future.value();
    return _rebuildComposite();
  }

  // 涂抹缓冲（画布收集，refine 时读取；尺寸=工作图）
  Uint8List? _fgScribble;
  Uint8List? _bgScribble;
  double _brushRadius = 6.0;
  void setBrushRadius(double r) {
    _brushRadius = r;
    state = state.copyWith(brushRadius: r);
  }

  /// 把 fg/bg 缓冲发布为显示缓冲（引用同一对象，只读），版本 +1 让叠层重绘。
  void _publishScribbleDisplay() {
    state = state.copyWith(
      fgDisplay: _fgScribble,
      bgDisplay: _bgScribble,
      scribbleVersion: state.scribbleVersion + 1,
    );
  }

  /// 清空涂抹（开始新一轮迭代前）。缓冲为工作图域尺寸，并清空画布叠层显示。
  void clearScribbles() {
    if (!_ensureWork()) return;
    _fgScribble = Uint8List(_workW * _workH);
    _bgScribble = Uint8List(_workW * _workH);
    // 重置笔触连线起点：新一笔不应与上一笔的末尾连线
    _lastFg = null; _lastBg = null;
    state = state.copyWith(
      clearScribbleDisplay: true,
      scribbleVersion: state.scribbleVersion + 1,
    );
  }

  // 每种笔色上一笔的掩码域坐标（用于相邻触摸点间插值补涂）。
  // 手指快速滑动时触摸回调稀疏，若只在每点画一个圆会留缝（虚线感）；
  // 在两点间按步长补涂可让笔触连续。抬起/清涂抹时重置，避免跨笔误连。
  (double, double)? _lastFg;
  (double, double)? _lastBg;

  /// 在工作图域 (mx,my) 处盖一个半径 r 的圆点进 buf。
  void _stamp(Uint8List buf, double mx, double my, double r, int w, int h) {
    final x0 = (mx - r).floor().clamp(0, w - 1), x1 = (mx + r).ceil().clamp(0, w - 1);
    final y0 = (my - r).floor().clamp(0, h - 1), y1 = (my + r).ceil().clamp(0, h - 1);
    final r2 = r * r;
    for (var yy = y0; yy <= y1; yy++) {
      for (var xx = x0; xx <= x1; xx++) {
        final dx = xx - mx, dy = yy - my;
        if (dx * dx + dy * dy <= r2) buf[yy * w + xx] = 255;
      }
    }
  }

  /// 涂抹一笔：原图像素坐标 (x,y)，内部映射到工作图域。fg=true 前景 / false 背景。
  /// 相邻两触摸点间按半径一半步长插值补涂，保证快速滑动时笔触连续（不留缝）。
  /// 每笔都同步进显示缓冲（叠层画点），多笔/前景背景全程保留，不再只看到上一步。
  void scribbleAt(double x, double y, {required bool fg}) {
    if (!_ensureWork()) return;
    _fgScribble ??= Uint8List(_workW * _workH);
    _bgScribble ??= Uint8List(_workW * _workH);
    final buf = fg ? _fgScribble! : _bgScribble!;
    final w = _workW, h = _workH;
    final p = _toMask(x, y);
    final mx = p.$1, my = p.$2;
    // 笔触半径也按比例缩到工作图域
    final img = _img!;
    final r = _brushRadius * _maskW / img.width;

    // 与上一笔连线插值：步长取半径一半（至少 0.5px），密集补涂消除缝隙
    final last = fg ? _lastFg : _lastBg;
    if (last != null) {
      final dx = mx - last.$1, dy = my - last.$2;
      final len = sqrt(dx * dx + dy * dy);
      final step = (r * 0.5).clamp(0.5, 4.0);
      if (len > step) {
        final n = (len / step).ceil();
        for (var i = 1; i <= n; i++) {
          final t = i / n;
          _stamp(buf, last.$1 + dx * t, last.$2 + dy * t, r, w, h);
        }
      }
    }
    _stamp(buf, mx, my, r, w, h);
    if (fg) { _lastFg = (mx, my); } else { _lastBg = (mx, my); }

    _publishScribbleDisplay();
  }

  /// 抬起结束一笔：重置笔触连线起点，下一笔不与本笔末尾连线（避免跨笔误连）。
  void endStroke() {
    _lastFg = null; _lastBg = null;
  }

  /// 提交涂抹并迭代分割。对应 refine（需已有初始分割）。
  Future<void> commitRefine() async {
    final fg = _fgScribble, bg = _bgScribble;
    final hasFg = fg != null && fg.any((v) => v > 0);
    final hasBg = bg != null && bg.any((v) => v > 0);
    if (!hasFg && !hasBg) { _status('请先在画布上涂抹前景/背景'); return; }
    await grabCutRefine(hasFg ? fg : null, hasBg ? bg : null);
    // refine 完成后清掉涂抹与画布痕迹，准备下一轮
    _fgScribble = null; _bgScribble = null;
    state = state.copyWith(
      clearScribbleDisplay: true,
      scribbleVersion: state.scribbleVersion + 1,
    );
  }

  /// 进入涂抹交互：清空上一轮痕迹，并默认切到高亮叠加画布上涂抹（若已有 mask）。
  void beginScribble() {
    clearScribbles();
    if (state.hasMask) {
      _ref.read(viewModeProvider.notifier).state = CanvasViewMode.highlight;
    }
  }

  // 撤销/重做栈（各存 8 步 mask 快照）
  static const _historyCap = 8;
  final List<Uint8List> _undo = [];
  final List<Uint8List> _redo = [];

  void _status(String m) => _ref.read(statusMessageProvider.notifier).state = m;

  /// 当前工作图（从 imageProvider 读），所有分割都作用在它上面。
  WorkingImage? get _img => _ref.read(imageProvider).working;

  // ---- 缩小工作图（关键：CV 在小图上跑，避免手机大图 OOM → cv_Mat_close SIGSEGV）----
  // 掩码在掩码域(maskW×maskH)维护，存入 state 前放大回原图尺寸供画布显示。
  // ---- 缩小工作图（关键：CV 在小图上跑，避免手机大图 OOM → cv_Mat_close SIGSEGV）----
  // 掩码在掩码域(maskW×maskH)维护，存入 state 前放大回原图尺寸供画布显示。
  //
  // 下采样目标分辨率跟随图纸尺寸：按奈奎斯特，图纸宽 Wg 豆的最高频率 ≈ Wg/2，
  // 处理分辨率 ≥ 2×Wg 即可无失真表达最终图纸；取 4×Wg 留 2× 余量保证边缘鲁棒。
  // 小图（原图已 ≤ 目标）不下采样，直接用原图；只在原图更大时才缩。
  // clamp(4×Wg, 256, 1024)：下限保证 GrabCut/GMM 有足够统计量，上限防大图 OOM/卡顿。
  static const _workMin = 256;
  static const _workMax = 1024;
  static const _nyquistFactor = 4;
  Uint8List? _workRgb;
  int _workW = 0, _workH = 0;
  int _maskW = 0, _maskH = 0; // 掩码域（= 工作图域）
  int _workSrcW = 0, _workSrcH = 0; // 缓存键：生成工作图时的原图尺寸
  int _workTarget = 0; // 缓存键：生成工作图时的目标边长

  /// 计算工作图目标边长：4×图纸宽，clamp 到 [256,1024]。
  int _targetWorkSide() {
    final (gw, _) = _ref.read(patternGridProvider);
    return (gw * _nyquistFactor).clamp(_workMin, _workMax);
  }

  /// 确保缩小工作图就绪。返回 false 表示无图。
  bool _ensureWork() {
    final img = _img;
    if (img == null) return false;
    final w = img.width, h = img.height;
    final target = _targetWorkSide();
    // 缓存有效：原图尺寸和目标边长都未变
    if (_workRgb != null && _workSrcW == w && _workSrcH == h && _workTarget == target) return true;
    // 只在最长边超过目标时才缩；小图直接用原分辨率
    final longest = w > h ? w : h;
    final scale = longest > target ? target / longest : 1.0;
    if (scale >= 1.0) {
      _workRgb = img.rgbBytes;
      _workW = w; _workH = h;
    } else {
      _workW = (w * scale).round().clamp(1, w);
      _workH = (h * scale).round().clamp(1, h);
      _workRgb = BasicAdjust.resizeRgb(img.rgbBytes, w, h, _workW, _workH);
    }
    _workSrcW = w; _workSrcH = h; _workTarget = target;
    final oldW = _maskW, oldH = _maskH;
    _maskW = _workW; _maskH = _workH;
    // 掩码域变了（图纸宽/原图变化 → 下采样目标变）。旧域与新域都是同一原图按不同
    // scale 下采样，宽高比一致，仅分辨率不同 —— 故旧 mask 可最近邻重采样到新域保留
    // 前景结构（不清空），避免「改图纸大小 / 生成图纸后切回 Mask 就消失」。
    // 撤销/重做栈与涂抹缓冲是逐帧旧域数据、跨域无意义，清空；GrabCut session 作废。
    _gcMask = null; _fgScribble = null; _bgScribble = null;
    _undo.clear(); _redo.clear();
    final oldMask = state.mask;
    if (oldMask != null && oldW > 0 && oldH > 0 && oldMask.length == oldW * oldH) {
      // 旧 mask 重采样到新域，保留分割结果
      final resized = BasicAdjust.resizeMask(oldMask, oldW, oldH, _workW, _workH);
      state.composite?.dispose();
      state = SegmentState(
        mask: resized,
        width: _workW,
        height: _workH,
        brushRadius: state.brushRadius,
        compositeVersion: state.compositeVersion + 1,
      );
      // 异步用新域 mask 重建合成显示图（沿用当前视图模式）
      _rebuildComposite();
    } else {
      // 无旧 mask（或域异常）→ 清空状态
      state.composite?.dispose();
      state = SegmentState(
        width: _workW,
        height: _workH,
        brushRadius: state.brushRadius,
        compositeVersion: state.compositeVersion + 1,
      );
    }
    return true;
  }

  /// 原图像素坐标 → 掩码域（计算域小图）坐标。
  (double, double) _toMask(double x, double y) {
    final img = _img!;
    return (x * _maskW / img.width, y * _maskH / img.height);
  }

  /// 提交分割结果。mask 全程是计算域小图尺寸（_workW×_workH），不放大回原图，
  /// 撤销/重做栈也都存小图（省内存）。显示交给 composite（也是小图）。
  void _commitMask(Uint8List maskDomain, {bool updateGc = false}) {
    if (updateGc) _gcMask = maskDomain;
    _pushHistory();
    _setMask(maskDomain, _workW, _workH);
    // 异步重建合成显示图（不阻塞分割返回）；分割完成后自动切到 mask 视图
    //（切视图发生在 composite 就绪之后，保证立刻有图）。
    _rebuildComposite(switchToMask: true);
  }

  void _pushHistory() {
    final m = state.mask;
    if (m == null) return;
    _undo.add(Uint8List.fromList(m));
    if (_undo.length > _historyCap) _undo.removeAt(0);
    _redo.clear();
    _syncCounts();
  }

  void _syncCounts() {
    state = state.copyWith(undoCount: _undo.length, redoCount: _redo.length);
  }

  void _setMask(Uint8List mask, int w, int h) {
    state = state.copyWith(mask: mask, width: w, height: h);
  }

  // ---------- 迭代 GrabCut ----------

  /// 初始分割：矩形 ROI。对应 segment_rect。坐标为原图像素，内部映射到工作图。
  Future<void> grabCutRect(int x, int y, int rw, int rh) async {
    if (!_ensureWork()) { _status('请先加载图像'); return; }
    if (rw < 2 || rh < 2) { _status('框选区域过小'); return; }
    // 映射矩形到工作图域
    final p0 = _toMask(x.toDouble(), y.toDouble());
    final p1 = _toMask((x + rw).toDouble(), (y + rh).toDouble());
    await _grabCutRectWork(p0.$1, p0.$2, p1.$1 - p0.$1, p1.$2 - p0.$2);
  }

  /// 矩形分割（工作图域坐标）。
  Future<void> _grabCutRectWork(double x, double y, double rw, double rh) async {
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在 GrabCut 矩形分割…');
    try {
      final wx = x.round().clamp(0, _workW - 1);
      final wy = y.round().clamp(0, _workH - 1);
      final ww = rw.round().clamp(2, _workW - wx);
      final wh = rh.round().clamp(2, _workH - wy);
      _bgdModel?.dispose(); _fgdModel?.dispose();
      final models = CvOps.newGrabCutModels();
      _bgdModel = models.$1; _fgdModel = models.$2;
      final mask = CvOps.grabCutRect(
          _workRgb!, _workH, _workW, wx, wy, ww, wh,
          _bgdModel!, _fgdModel!, iters: 5);
      state = state.copyWith(busy: false, hasGrabCutSession: true);
    _ref.read(busyProvider.notifier).refresh();
      _commitMask(mask, updateGc: true);
      _status('初始分割完成，可涂抹前景/背景后迭代');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('GrabCut 失败：$e');
    }
  }

  /// 初始分割：自由涂抹 mask 作为种子（PR_FGD）。对应 segment_mask。
  /// [seedMask] 为掩码域（_workW×_workH）的 GC_* 标签。
  Future<void> grabCutFromMask(Uint8List seedMask) async {
    if (!_ensureWork()) { _status('请先加载图像'); return; }
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在 GrabCut 分割…');
    try {
      _bgdModel?.dispose(); _fgdModel?.dispose();
      final models = CvOps.newGrabCutModels();
      _bgdModel = models.$1; _fgdModel = models.$2;
      final mask = CvOps.grabCutMask(
          _workRgb!, _workH, _workW, seedMask, _bgdModel!, _fgdModel!,
          iters: 5);
      state = state.copyWith(busy: false, hasGrabCutSession: true);
    _ref.read(busyProvider.notifier).refresh();
      _commitMask(mask, updateGc: true);
      _status('初始分割完成，可涂抹前景/背景后迭代');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('GrabCut 失败：$e');
    }
  }

  /// 初始分割统一入口：按形状分派。矩形走 rect（更高效），
  /// 椭圆/自由曲线先转种子 mask 再走 mask 路径。
  /// [points] 为原图像素坐标；内部映射到工作图域再生成种子。
  Future<void> grabCutSelect(SelectShape shape, List<(double, double)> points) async {
    if (!_ensureWork()) { _status('请先加载图像'); return; }
    if (points.isEmpty) { _status('请先在画布上框选'); return; }
    final w = _workW, h = _workH;
    // 映射到工作图域
    final pts = points.map((p) => _toMask(p.$1, p.$2)).toList();
    double minX() => pts.map((p) => p.$1).reduce((a, b) => a < b ? a : b);
    double maxX() => pts.map((p) => p.$1).reduce((a, b) => a > b ? a : b);
    double minY() => pts.map((p) => p.$2).reduce((a, b) => a < b ? a : b);
    double maxY() => pts.map((p) => p.$2).reduce((a, b) => a > b ? a : b);

    if (shape == SelectShape.rect) {
      final x0 = minX().clamp(0.0, w - 1.0), y0 = minY().clamp(0.0, h - 1.0);
      final x1 = maxX().clamp(0.0, w - 1.0), y1 = maxY().clamp(0.0, h - 1.0);
      await _grabCutRectWork(x0, y0,
          (x1 - x0).clamp(2.0, w.toDouble()), (y1 - y0).clamp(2.0, h.toDouble()));
      return;
    }
    // 椭圆 / 自由曲线 → 种子 mask（区域内=PR_FGD，其余默认 BGD 交 grabCut 判定）
    final seed = Uint8List(w * h);
    if (shape == SelectShape.ellipse) {
      final cx = (minX() + maxX()) / 2, cy = (minY() + maxY()) / 2;
      final rx = ((maxX() - minX()) / 2).clamp(1.0, w.toDouble());
      final ry = ((maxY() - minY()) / 2).clamp(1.0, h.toDouble());
      for (var y = 0; y < h; y++) {
        for (var x = 0; x < w; x++) {
          final dx = (x - cx) / rx, dy = (y - cy) / ry;
          if (dx * dx + dy * dy <= 1.0) seed[y * w + x] = cv.GC_PR_FGD;
        }
      }
    } else {
      // 自由曲线：射线法填充轨迹多边形为 PR_FGD
      for (var y = 0; y < h; y++) {
        for (var x = 0; x < w; x++) {
          if (_pointInPolygon(x + 0.5, y + 0.5, pts)) seed[y * w + x] = cv.GC_PR_FGD;
        }
      }
    }
    await grabCutFromMask(seed);
  }

  static bool _pointInPolygon(double px, double py, List<(double, double)> pts) {
    var inside = false;
    for (var i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      final xi = pts[i].$1, yi = pts[i].$2;
      final xj = pts[j].$1, yj = pts[j].$2;
      final denom = (yj - yi) == 0 ? 1e-9 : (yj - yi);
      final hit = ((yi > py) != (yj > py)) && (px < (xj - xi) * (py - yi) / denom + xi);
      if (hit) inside = !inside;
    }
    return inside;
  }

  /// 迭代分割：用前景/背景涂抹修正。对应 refine。
  /// [fgScribble]/[bgScribble] 为掩码域（_workW×_workH）字节，>0 表示涂抹处。
  Future<void> grabCutRefine(Uint8List? fgScribble, Uint8List? bgScribble) async {
    if (!_ensureWork()) { _status('请先加载图像'); return; }
    if (!state.hasGrabCutSession || _gcMask == null || _bgdModel == null) {
      _status('请先完成初始分割'); return;
    }
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在迭代分割…');
    try {
      final h = _workH, w = _workW;
      // 组装 GC_* 标签：默认 PR_BGD；上结果作 PR_FGD；涂抹覆盖 FGD/BGD。
      final gc = Uint8List(h * w);
      for (var i = 0; i < h * w; i++) {
        gc[i] = _gcMask![i] > 0 ? cv.GC_PR_FGD : cv.GC_PR_BGD;
      }
      if (fgScribble != null) {
        for (var i = 0; i < h * w; i++) { if (fgScribble[i] > 0) gc[i] = cv.GC_FGD; }
      }
      if (bgScribble != null) {
        for (var i = 0; i < h * w; i++) { if (bgScribble[i] > 0) gc[i] = cv.GC_BGD; }
      }
      final mask = CvOps.grabCutMask(
          _workRgb!, h, w, gc, _bgdModel!, _fgdModel!, iters: 3);
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _commitMask(mask, updateGc: true);
      _status('迭代完成');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('迭代失败：$e');
    }
  }

  // ---------- 自动分割 ----------

  Future<void> autoSegment(String method, {double fgRatio = 0.4, int superpixels = 150}) async {
    if (!_ensureWork()) { _status('请先加载图像'); return; }
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在自动分割（$method）…');
    try {
      final h = _workH, w = _workW;
      final rgb = _workRgb!;
      Uint8List mask;
      var isGc = false;
      switch (method) {
        case 'grabcut_rect':
          _bgdModel?.dispose(); _fgdModel?.dispose();
          final models = CvOps.newGrabCutModels();
          _bgdModel = models.$1; _fgdModel = models.$2;
          // 中央 80% 矩形作为初始框
          final mx = (w * 0.1).round(), my = (h * 0.1).round();
          mask = CvOps.grabCutRect(rgb, h, w, mx, my, w - 2 * mx, h - 2 * my,
              _bgdModel!, _fgdModel!, iters: 5);
          isGc = true;
          state = state.copyWith(hasGrabCutSession: true);
          break;
        case 'otsu':
          mask = CvOps.otsuSegment(rgb, h, w);
          break;
        case 'slic':
          mask = _slicSegment(rgb, h, w, superpixels);
          break;
        case 'watershed':
        default:
          mask = CvOps.watershedAuto(rgb, h, w, fgRatio: fgRatio);
      }
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _commitMask(mask, updateGc: isGc);
      _status('自动分割完成');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('自动分割失败：$e');
    }
  }

  /// SLIC 分割 → 聚合为前景 mask。对应 slic_segment（纯 Dart SLIC + Otsu 聚合）。
  Uint8List _slicSegment(Uint8List rgb, int h, int w, int nSegments) {
    final segments = Slic.slicSuperpixels(rgb, h, w, nSegments: nSegments);
    return CvOps.slicAggregate(rgb, h, w, segments);
  }

  // ---------- 形态学 ----------

  static const _morphOps = ['open', 'close', 'erode', 'dilate'];
  static const _morphShapes = ['ellipse', 'rect', 'cross', 'vline', 'hline', 'diamond'];

  Future<void> applyMorph(int opIndex, int kernelSize, int shapeIndex) async {
    final m = state.mask;
    if (m == null) { _status('请先分割生成 Mask'); return; }
    if (!_ensureWork()) return;
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    try {
      final op = _morphOps[opIndex.clamp(0, _morphOps.length - 1)];
      final shape = _morphShapes[shapeIndex.clamp(0, _morphShapes.length - 1)];
      // state.mask 已是计算域小图尺寸，直接用（无需任何缩放往返）
      final result = CvOps.morphology(m, _maskH, _maskW, op, kernelSize, shape);
      // 保护：形态学结果若已无任何前景（腐蚀/开运算把细碎前景抹没），不提交这步，
      // 保留原 mask 并提示减小核——否则整个 Mask 变全背景、还得撤销找回。
      var fgCount = 0;
      for (var i = 0; i < result.length; i++) {
        if (result[i] > 127) fgCount++;
      }
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      if (fgCount == 0) {
        _status('形态学（$op）已抹去全部前景，未应用；请减小核大小');
        return;
      }
      _commitMask(result, updateGc: state.hasGrabCutSession);
      _status('形态学已应用（$op）');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('形态学失败：$e');
    }
  }

  // ---------- 撤销 / 重做 ----------

  void undo() {
    if (_undo.isEmpty) { _status('没有可撤销的操作'); return; }
    final cur = state.mask;
    if (cur != null) _redo.add(Uint8List.fromList(cur));
    final prev = _undo.removeLast();
    // 快照都是计算域小图，直接还原，session 的 gcMask 也用同一小图
    _setMask(prev, state.width, state.height);
    if (state.hasGrabCutSession && _ensureWork()) _gcMask = prev;
    _syncCounts();
    _status('已撤销');
    _rebuildComposite();
  }

  void redo() {
    if (_redo.isEmpty) { _status('没有可重做的操作'); return; }
    final cur = state.mask;
    if (cur != null) _undo.add(Uint8List.fromList(cur));
    final next = _redo.removeLast();
    _setMask(next, state.width, state.height);
    if (state.hasGrabCutSession && _ensureWork()) _gcMask = next;
    _syncCounts();
    _status('已重做');
    _rebuildComposite();
  }

  /// 清空分割（图像更换/恢复时调用）。
  void reset() {
    _bgdModel?.dispose(); _fgdModel?.dispose();
    _bgdModel = null; _fgdModel = null; _gcMask = null;
    _undo.clear(); _redo.clear();
    _workRgb = null; _workW = 0; _workH = 0; _maskW = 0; _maskH = 0;
    _workSrcW = 0; _workSrcH = 0; _workTarget = 0;
    _fgScribble = null; _bgScribble = null;
    state.composite?.dispose();
    state = const SegmentState();
  }
}

final segmentProvider =
    StateNotifierProvider<SegmentNotifier, SegmentState>((ref) => SegmentNotifier(ref));

// ======================= 图纸生成（M3） =======================

/// 图纸状态：豆网格参数 + 量化豆图 + codes + beadMask + BOM + 渲染好的图纸 ui.Image。
/// 量化在豆域（gw×gh ≈ 万级像素）纯 Dart 跑，毫秒~百毫秒级；图纸用 ChartPainter
/// 离线录制一次成 ui.Image，画布直接显示（与分割 composite 同一思路：零逐帧计算）。
class PatternState {
  final int gw; // 图纸宽（豆）
  final int gh; // 图纸高（豆）
  final List<String> codes; // 每豆 code（gw*gh）
  final List<bool>? beadMask; // 前景保留豆（gw*gh）；null = 不用 mask
  final List<BomEntry> bom; // BOM（count desc）
  final int totalBeads; // 总豆数（mask 时为前景豆数）
  final ui.Image? chartImage; // 渲染好的完整图纸
  final int version; // 每次生成 +1，画布据此刷新
  final bool busy;
  const PatternState({
    this.gw = 0,
    this.gh = 0,
    this.codes = const [],
    this.beadMask,
    this.bom = const [],
    this.totalBeads = 0,
    this.chartImage,
    this.version = 0,
    this.busy = false,
  });

  bool get hasPattern => chartImage != null;

  PatternState copyWith({
    int? gw,
    int? gh,
    List<String>? codes,
    List<bool>? beadMask,
    List<BomEntry>? bom,
    int? totalBeads,
    ui.Image? chartImage,
    int? version,
    bool? busy,
    bool clearBeadMask = false,
    bool clearChart = false,
  }) =>
      PatternState(
        gw: gw ?? this.gw,
        gh: gh ?? this.gh,
        codes: codes ?? this.codes,
        beadMask: clearBeadMask ? null : (beadMask ?? this.beadMask),
        bom: bom ?? this.bom,
        totalBeads: totalBeads ?? this.totalBeads,
        chartImage: clearChart ? null : (chartImage ?? this.chartImage),
        version: version ?? this.version,
        busy: busy ?? this.busy,
      );
}

/// 图纸引擎：下采样 → 量化 → codes → beadMask → BOM → 渲染。
/// 数据流对齐桌面版 app.py:pattern_generate + pattern_generator.render_standard_chart。
/// 全程纯 Dart（不碰 OpenCV native，避开部分 ABI 的 SIGSEGV）。
class PatternNotifier extends StateNotifier<PatternState> {
  PatternNotifier(this._ref) : super(const PatternState());
  final Ref _ref;

  final Map<String, Palette> _palettes = {}; // 按品牌缓存调色板（异步加载一次）

  void _status(String m) => _ref.read(statusMessageProvider.notifier).state = m;

  /// 确保当前品牌的调色板就绪。
  Future<Palette> _ensurePalette(String metric) async {
    final brand = _ref.read(brandProvider);
    final p = _palettes[brand] ??= await Palette.loadBrand(brand);
    p.metric = metric;
    return p;
  }

  /// 生成图纸。对应桌面版 pattern_generate + render_standard_chart 一次到位。
  /// [colorLimit] null/0 = 不限色；[useMask] 且有分割 mask 时背景豆淡化、BOM 只计前景。
  /// [maskBg] none/white/black（对应桌面 MASK 背景：淡化/纯白/纯黑）。
  Future<void> generate({
    required int gw,
    required int gh,
    int? colorLimit,
    double salience = 1.0,
    String metric = 'ciede2000',
    bool dither = false,
    double ditherStrength = 1.0,
    double icmSmooth = 0.0,
    bool useMask = true,
    String maskBg = 'none',
  }) async {
    final img = _ref.read(imageProvider).working;
    if (img == null) {
      _status('请先加载图像');
      return;
    }
    gw = gw.clamp(1, 512);
    gh = gh.clamp(1, 512);
    state = state.copyWith(busy: true);
    _ref.read(busyProvider.notifier).refresh();
    _status('正在生成图纸（$gw×$gh）…');
    try {
      final palette = await _ensurePalette(metric);

      // 1) 大图 → 豆域小图（盒式平均 = cv2.INTER_AREA，避免高色限摩尔纹）
      final beadRgb = PatternRender.boxAverageDownsample(
          img.rgbBytes, img.width, img.height, gw, gh);

      // 2) 量化（豆域，毫秒级）
      final qres = Quantizer(palette).quantize(
        beadRgb, gh, gw,
        colorLimit: (colorLimit == null || colorLimit <= 0) ? null : colorLimit,
        salience: salience,
        dither: dither,
        ditherStrength: ditherStrength,
        icmSmooth: icmSmooth,
      );

      // 3) 逐豆 code
      final codes = PatternRender.buildCodes(palette, qres.rgb, gw, gh);

      // 4) beadMask：useMask 且有分割 mask 时，把 mask 对齐到豆网格
      //    （对称清写：不勾/无 mask 一律 null，不残留旧遮罩 → 对齐桌面修复）
      List<bool>? beadMask;
      final seg = _ref.read(segmentProvider);
      if (useMask && seg.mask != null) {
        beadMask = PatternRender.maskToBeadGrid(
            seg.mask!, seg.width, seg.height, gw, gh);
      }

      // 5) BOM（mask 时只计前景）
      final bom = PatternRender.buildBom(
        palette, qres.usage, gw * gh,
        beadMask: beadMask, codes: codes,
      );
      final totalBeads =
          beadMask == null ? gw * gh : beadMask.where((b) => b).length;

      // 6) 渲染完整图纸（离线录制一次成 ui.Image）
      final chart = await ChartPainter.render(
        quantRgb: qres.rgb,
        gw: gw,
        gh: gh,
        codes: codes,
        palette: palette,
        bom: bom,
        beadMask: beadMask,
        fadeMasked: maskBg == 'none',
        maskBg: maskBg,
        title: _ref.read(showChartTitleProvider)
            ? (_ref.read(exportNameProvider).trim().isNotEmpty
                ? _ref.read(exportNameProvider).trim()
                : _ref.read(sourceNameProvider))
            : null,
        brand: Palette.brandLabels[_ref.read(brandProvider)],
        colorCount: bom.length,
        totalBeads: totalBeads,
      );

      // 成功：dispose 旧图纸 + version+1，就绪后再切到图纸视图（仿分割自动切 mask）
      state.chartImage?.dispose();
      state = state.copyWith(
        gw: gw,
        gh: gh,
        codes: codes,
        beadMask: beadMask,
        clearBeadMask: beadMask == null,
        bom: bom,
        totalBeads: totalBeads,
        chartImage: chart,
        version: state.version + 1,
        busy: false,
      );
      _ref.read(busyProvider.notifier).refresh();
      _ref.read(viewModeProvider.notifier).state = CanvasViewMode.pattern;
      _status('图纸已生成：$gw×$gh · ${bom.length} 色 · $totalBeads 豆');
    } catch (e) {
      state = state.copyWith(busy: false);
      _ref.read(busyProvider.notifier).refresh();
      _status('图纸生成失败：$e');
    }
  }

  /// 清空图纸（图像更换/恢复时调用）。
  void reset() {
    state.chartImage?.dispose();
    state = const PatternState();
  }
}

final patternProvider =
    StateNotifierProvider<PatternNotifier, PatternState>((ref) => PatternNotifier(ref));
