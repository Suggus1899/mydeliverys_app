import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';

/// Carrito mono-restaurante con persistencia inmediata en Hive (offline-first).
/// RF-CLI-26..29. Backend recalcula todo en POST /orders/draft (nunca confia precios locales).

class CartItem {
  final String productId;
  final String restaurantId;
  final String name;
  final int quantity;
  final List<String> modifierIds;

  const CartItem({
    required this.productId,
    required this.restaurantId,
    required this.name,
    this.quantity = 1,
    this.modifierIds = const [],
  });

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'restaurant_id': restaurantId,
        'name': name,
        'quantity': quantity,
        'modifier_ids': modifierIds,
      };

  factory CartItem.fromJson(Map<String, dynamic> j) => CartItem(
        productId: j['product_id'] as String,
        restaurantId: j['restaurant_id'] as String,
        name: j['name'] as String,
        quantity: (j['quantity'] as num).toInt(),
        modifierIds: ((j['modifier_ids'] as List?) ?? []).cast<String>(),
      );
}

class CartState {
  final List<CartItem> items;
  final String? restaurantId;
  final String? restaurantName;
  const CartState({this.items = const [], this.restaurantId, this.restaurantName});

  bool get isEmpty => items.isEmpty;
  int get count => items.fold(0, (a, i) => a + i.quantity);
}

/// Devuelve 'conflict' si el producto es de otro restaurante (la UI muestra modal).
enum CartAddResult { added, conflict }

class CartController extends StateNotifier<CartState> {
  final Box box;
  CartController(this.box) : super(const CartState()) {
    _restore();
  }

  void _restore() {
    final raw = box.get('active_cart') as Map?;
    if (raw == null) return;
    final items = ((raw['items'] as List?) ?? []).map((e) => CartItem.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    state = CartState(
      items: items,
      restaurantId: raw['restaurant_id'] as String?,
      restaurantName: raw['restaurant_name'] as String?,
    );
  }

  void _persist() {
    box.put('active_cart', {
      'restaurant_id': state.restaurantId,
      'restaurant_name': state.restaurantName,
      'items': state.items.map((e) => e.toJson()).toList(),
    });
  }

  CartAddResult add(CartItem item, {String? restaurantName, bool confirmedReplace = false}) {
    if (state.restaurantId != null && state.restaurantId != item.restaurantId && !confirmedReplace) {
      return CartAddResult.conflict;
    }
    final base = confirmedReplace || state.restaurantId != item.restaurantId ? <CartItem>[] : [...state.items];
    base.add(item);
    state = CartState(items: base, restaurantId: item.restaurantId, restaurantName: restaurantName ?? state.restaurantName);
    _persist();
    return CartAddResult.added;
  }

  void removeAt(int index) {
    final next = [...state.items]..removeAt(index);
    state = next.isEmpty ? const CartState() : CartState(items: next, restaurantId: state.restaurantId, restaurantName: state.restaurantName);
    _persist();
  }

  void clear() {
    state = const CartState();
    box.delete('active_cart');
  }
}

final cartControllerProvider = StateNotifierProvider<CartController, CartState>((ref) {
  throw UnimplementedError('Inicializar con Hive box en main()');
});
