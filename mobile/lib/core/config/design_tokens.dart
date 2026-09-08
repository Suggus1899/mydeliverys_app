import 'package:flutter/material.dart';

/// Design System "Apetito Calido y Confiable" — docs/sdd/design_system.md
/// Light Theme First V1. Primario reservado a accion principal.
abstract final class DesignTokens {
  // Primario
  static const primary500 = Color(0xFFFF5A36);
  static const primary600 = Color(0xFFE04422);
  static const primary100 = Color(0xFFFFEBE6);

  // Textos
  static const textPrimary = Color(0xFF1E2229);
  static const textSecondary = Color(0xFF5A6270);
  static const textTertiary = Color(0xFF8C95A6);

  // Fondos
  static const backgroundCanvas = Color(0xFFF8F9FA);
  static const surfaceCard = Color(0xFFFFFFFF);
  static const borderSubtle = Color(0xFFE9ECEF);

  // Funcionales
  static const success500 = Color(0xFF10B981);
  static const success100 = Color(0xFFD1FAE5);
  static const warning500 = Color(0xFFF59E0B);
  static const warning100 = Color(0xFFFEF3C7);
  static const error500 = Color(0xFFDC2626);
  static const error100 = Color(0xFFFEE2E2);
  static const infoPrep = Color(0xFF2563EB);
  static const infoTransit = Color(0xFF7C3AED);

  // Radios
  static const radiusCard = 16.0;
  static const radiusBottomSheet = 24.0;
  static const radiusButton = 12.0;

  // Tipografia
  static const fontDisplay = 'Outfit';
  static const fontBody = 'Inter';

  /// Montos SIEMPRE con cifras tabulares para que $7.51 vs $7.50 no bailen.
  static TextStyle money(double size, {FontWeight weight = FontWeight.w700, Color color = textPrimary}) {
    return TextStyle(
      fontFamily: fontBody,
      fontSize: size,
      fontWeight: weight,
      color: color,
      fontFeatures: const [FontFeature.tabularFigures()],
    );
  }
}

/// Variante Solar exclusiva Driver: fondo blanco puro, negro absoluto, touch 56dp.
abstract final class SolarTokens {
  static const background = Color(0xFFFFFFFF);
  static const textPrimary = Color(0xFF000000);
  static const textSecondary = Color(0xFF333333);
  static const accent = Color(0xFFFF5A36);
  static const minTouch = 56.0;
}
