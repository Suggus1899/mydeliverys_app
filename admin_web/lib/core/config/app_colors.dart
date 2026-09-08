import 'package:flutter/material.dart';

/// Tokens compartidos con la app movil ("Apetito Calido y Confiable").
/// La web usa EXACTAMENTE los mismos colores que la app:
/// primario #FF5A36, textos #1E2229, fondo #F8F9FA, tarjetas #FFFFFF.
/// Decision V1: tema claro por defecto en consola y kanban; variante
/// oscura industrial disponible como opt-in (ConsoleDark).
abstract final class AppColors {
  // Primario (moderacion: solo accion principal)
  static const primary500 = Color(0xFFFF5A36);
  static const primary600 = Color(0xFFE04422);
  static const primary100 = Color(0xFFFFEBE6);

  // Textos y fondos (identicos a la app)
  static const textPrimary = Color(0xFF1E2229);
  static const textSecondary = Color(0xFF5A6270);
  static const textTertiary = Color(0xFF8C95A6);
  static const background = Color(0xFFF8F9FA);
  static const surface = Color(0xFFFFFFFF);
  static const card = Color(0xFFFFFFFF);
  static const border = Color(0xFFE9ECEF);

  // Funcionales (identicos a la app)
  static const accent = primary500;
  static const success = Color(0xFF10B981);
  static const successBg = Color(0xFFD1FAE5);
  static const warning = Color(0xFFF59E0B);
  static const warningBg = Color(0xFFFEF3C7);
  static const danger = Color(0xFFDC2626);
  static const dangerBg = Color(0xFFFEE2E2);
  static const info = Color(0xFF2563EB);

  /// Montos SIEMPRE con cifras tabulares (regla financiera global).
  static TextStyle money(double size, {Color color = textPrimary}) => TextStyle(
        fontSize: size,
        fontWeight: FontWeight.w700,
        color: color,
        fontFeatures: const [FontFeature.tabularFigures()],
      );
}

/// Variante oscura industrial (opt-in): misma que spec 05 original.
/// Se mantiene para operacion nocturna; por defecto la web usa [AppColors].
abstract final class ConsoleDark {
  static const background = Color(0xFF0B0E14);
  static const surface = Color(0xFF151A24);
  static const card = Color(0xFF1C2230);
  static const border = Color(0xFF2A3348);
  static const textPrimary = Color(0xFFE8ECF3);
  static const textSecondary = Color(0xFF9AA5B8);
  static const accent = Color(0xFFFF5A36);
  static const success = Color(0xFF10B981);
  static const warning = Color(0xFFF59E0B);
  static const danger = Color(0xFFDC2626);
  static const info = Color(0xFF2563EB);
}
