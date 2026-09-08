/// Dinero en unidades menores enteras (centavos USD / centesimas VES).
/// El backend transmite Decimal como string; Dart NUNCA usa double para dinero.
class Money {
  final int minorUnits;
  final String currency; // 'USD' | 'VES'

  const Money(this.minorUnits, {this.currency = 'USD'});

  factory Money.fromBackendString(String decimalStr, {String currency = 'USD'}) {
    final parts = decimalStr.split('.');
    final whole = int.parse(parts[0]);
    final cents = parts.length > 1 ? parts[1].padRight(2, '0').substring(0, 2) : '00';
    final sign = whole < 0 || decimalStr.startsWith('-') ? -1 : 1;
    return Money((whole.abs() * 100 + int.parse(cents)) * sign, currency: currency);
  }

  String get asBackendString {
    final sign = minorUnits < 0 ? '-' : '';
    final abs = minorUnits.abs();
    return '$sign${abs ~/ 100}.${(abs % 100).toString().padLeft(2, '0')}';
  }

  String get display => '${currency == 'USD' ? '\$' : 'Bs. '}$asBackendString';

  Money operator +(Money other) {
    assert(currency == other.currency);
    return Money(minorUnits + other.minorUnits, currency: currency);
  }
}

/// Division 50/50 con centavo impar al primer pago (solo display; el backend manda).
({Money first, Money second}) split5050(Money total) {
  if (total.minorUnits < 0) {
    throw ArgumentError.value(total.minorUnits, 'total', 'Debe ser no negativo');
  }
  final firstMinor = (total.minorUnits + 1) ~/ 2;
  return (
    first: Money(firstMinor, currency: total.currency),
    second: Money(total.minorUnits - firstMinor, currency: total.currency),
  );
}
