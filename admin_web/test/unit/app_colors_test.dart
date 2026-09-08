import 'package:flutter_test/flutter_test.dart';
import 'package:mydeliverys_admin/core/config/app_colors.dart';

/// La web debe usar EXACTAMENTE los mismos colores que la app movil.
void main() {
  test('tokens web identicos a app movil', () {
    expect(AppColors.primary500.toARGB32(), 0xFFFF5A36);
    expect(AppColors.textPrimary.toARGB32(), 0xFF1E2229);
    expect(AppColors.background.toARGB32(), 0xFFF8F9FA);
    expect(AppColors.surface.toARGB32(), 0xFFFFFFFF);
    expect(AppColors.success.toARGB32(), 0xFF10B981);
    expect(AppColors.warning.toARGB32(), 0xFFF59E0B);
    expect(AppColors.danger.toARGB32(), 0xFFDC2626);
  });
}
