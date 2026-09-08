import '../../../core/network/api_client.dart';

class DriverRepository {
  const DriverRepository(this._api);
  final ApiClient _api;

  Future<void> setAvailable(bool available) => _api.patch(
        '/driver/availability?is_available=$available',
        (_) {},
      );

  Future<List<Map<String, dynamic>>> availableOrders() => _api.get(
        '/driver/orders/available',
        (raw) => (raw! as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList(),
      );

  Future<Map<String, dynamic>> action(String orderId, String action) => _api.post(
        '/driver/orders/$orderId/$action',
        (raw) => Map<String, dynamic>.from(raw! as Map),
        idempotent: true,
      );

  Future<Map<String, dynamic>> collectCash(
    String orderId, {
    required String amountUsd,
    String? amountVes,
  }) =>
      _api.post(
        '/driver/orders/$orderId/collect-cash',
        (raw) => Map<String, dynamic>.from(raw! as Map),
        idempotent: true,
        body: {
          'amount_usd': amountUsd,
          if (amountVes != null && amountVes.isNotEmpty) 'amount_ves': amountVes,
        },
      );

  Future<Map<String, dynamic>> reportDigital(
    String orderId, {
    required String reference,
    required String bank,
  }) =>
      _api.post(
        '/driver/orders/$orderId/confirm-digital',
        (raw) => Map<String, dynamic>.from(raw! as Map),
        idempotent: true,
        body: {'reference_number': reference, 'origin_bank': bank},
      );

  Future<void> publishLocation(
    String orderId,
    String latitude,
    String longitude,
    String? heading,
  ) =>
      _api.post(
        '/tracking/location',
        (_) {},
        body: {
          'order_id': orderId,
          'latitude': latitude,
          'longitude': longitude,
          if (heading != null) 'heading': heading,
        },
      );
}
