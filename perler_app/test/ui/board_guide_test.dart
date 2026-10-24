import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:perler_app/theme/candy_theme.dart';
import 'package:perler_app/ui/board/board_guide.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('首次引导可翻页并完成，完成后写入已读标记', (tester) async {
    SharedPreferences.setMockInitialValues({});
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(
      theme: buildCandyTheme(Brightness.light),
      home: Scaffold(body: Builder(builder: (ctx) {
        context = ctx;
        return const SizedBox();
      })),
    ));
    final shown = BoardGuideDialog.showIfFirstUse(context);
    await tester.pumpAndSettle();
    expect(find.text('上传与更换底图'), findsOneWidget);
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.text('下一步'));
      await tester.pumpAndSettle();
    }
    expect(find.text('导出图纸'), findsOneWidget);
    await tester.tap(find.text('开始绘制'));
    await shown;
    await tester.pumpAndSettle();
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool(BoardGuideDialog.seenKey), isTrue);
  });

  testWidgets('已读用户不会再次自动弹出引导', (tester) async {
    SharedPreferences.setMockInitialValues({BoardGuideDialog.seenKey: true});
    late BuildContext context;
    await tester.pumpWidget(MaterialApp(
      theme: buildCandyTheme(Brightness.light),
      home: Scaffold(body: Builder(builder: (ctx) {
        context = ctx;
        return const SizedBox();
      })),
    ));
    await BoardGuideDialog.showIfFirstUse(context);
    await tester.pumpAndSettle();
    expect(find.text('图纸画板 · 新手引导'), findsNothing);
  });
}
