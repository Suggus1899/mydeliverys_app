import '../../../core/network/api_client.dart';
import '../../cart/cart_controller.dart';

class DeliveryRepository {
  const DeliveryRepository(this._api);
  final ApiClient _api;

  Future<List<Map<String, dynamic>>> restaurants() => _api.get(
        '/restaurants',
        (raw) => (raw! as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList(),
      );

  Future<Map<String, dynamic>> menu(String restaurantId) => _api.get(
        '/restaurants/$restaurantId/menu',
        (raw) => Map<String, dynamic>.from(raw! as Map),
      );

  Future<List<Map<String, dynamic>>> addresses() => _api.get(
        '/users/me/addresses',
        (raw) => (raw! as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList(),
      );

  Future<Map<String, dynamic>> createDraft(List<CartItem> items, String addressId) =>
      _api.post(
        '/orders/draft',
        (raw) => Map<String, dynamic>.from(raw! as Map),
        idempotent: true,
        body: {
          'address_id': addressId,
          'items': [
            for (final item in items)
              {
                'product_id': item.productId,
                'quantity': item.quantity,
                'modifiers': [
                  for (final id in item.modifierIds) {'modifier_id': id},
                ],
              },
          ],
        },
      );

  Future<List<Map<String, dynamic>>> orders() => _api.get(
        '/orders',
        (raw) => (raw! as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList(),
      );
}
