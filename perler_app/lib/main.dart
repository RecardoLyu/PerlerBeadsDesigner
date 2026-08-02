import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'theme/candy_theme.dart';
import 'state/app_state.dart';
import 'ui/home_screen.dart';

void main() {
  runApp(const ProviderScope(child: PerlerApp()));
}

class PerlerApp extends ConsumerWidget {
  const PerlerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    return MaterialApp(
      title: '拼豆图纸生成器',
      debugShowCheckedModeBanner: false,
      theme: buildCandyTheme(Brightness.light),
      darkTheme: buildCandyTheme(Brightness.dark),
      themeMode: mode,
      home: const HomeScreen(),
    );
  }
}
