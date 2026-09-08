import 'package:flutter/material.dart';

ThemeData appTheme({bool solar = false}) {
  const primary = Color(0xFFFF5A36);
  final background = solar ? const Color(0xFFFFFFFF) : const Color(0xFFF8F9FA);
  return ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: background,
    colorScheme: ColorScheme.fromSeed(seedColor: primary, surface: background),
    textTheme: const TextTheme().apply(fontFamily: 'Inter', bodyColor: const Color(0xFF1E2229)),
    appBarTheme: const AppBarTheme(titleTextStyle: TextStyle(fontFamily: 'Outfit', fontSize: 22, color: Color(0xFF1E2229), fontWeight: FontWeight.w600)),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(minimumSize: const Size(48, 52)),
    ),
    visualDensity: solar ? VisualDensity.comfortable : VisualDensity.standard,
  );
}

const moneyStyle = TextStyle(
  fontFamily: 'Inter',
  fontFeatures: [FontFeature.tabularFigures()],
  fontWeight: FontWeight.w700,
);
