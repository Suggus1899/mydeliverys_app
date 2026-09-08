import 'package:flutter_test/flutter_test.dart';
import 'package:mydeliverys_mobile/shared/models/money.dart';

void main() {
  group('Money.fromBackendString', () {
    test('parsea 15.01 a 1501 centavos', () {
      expect(Money.fromBackendString('15.01').minorUnits, 1501);
    });

    test('round-trip conserva valor', () {
      for (final s in ['20.00', '7.51', '7.50', '0.01', '0.00']) {
        expect(Money.fromBackendString(s).asBackendString, s);
      }
    });
  });

  group('split5050 (solo display, backend manda)', () {
    test('15.01 -> 7.51 + 7.50', () {
      final total = Money.fromBackendString('15.01');
      final parts = split5050(total);
      expect(parts.first.asBackendString, '7.51');
      expect(parts.second.asBackendString, '7.50');
    });

    test('0.01 -> 0.01 + 0.00', () {
      final total = Money.fromBackendString('0.01');
      final parts = split5050(total);
      expect(parts.first.asBackendString, '0.01');
      expect(parts.second.asBackendString, '0.00');
    });
  });
}
