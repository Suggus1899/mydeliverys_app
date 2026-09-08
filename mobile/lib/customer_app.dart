import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'app_theme.dart';
import 'core/providers.dart';
import 'features/auth/presentation/auth_screen.dart';
import 'features/cart/cart_controller.dart';
import 'features/delivery/data/delivery_repository.dart';

final deliveryRepositoryProvider = Provider<DeliveryRepository>(
  (ref) => DeliveryRepository(ref.watch(apiClientProvider)),
);

class CustomerApp extends ConsumerWidget {
  const CustomerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loggedIn = ref.watch(accessTokenProvider) != null;
    final router = GoRouter(
      initialLocation: loggedIn ? '/' : '/acceso',
      routes: [
        GoRoute(
          path: '/acceso',
          builder: (context, state) => AuthScreen(
            partner: false,
            onAuthenticated: () => context.go('/'),
          ),
        ),
        GoRoute(path: '/', builder: (context, state) => const CustomerHome()),
        GoRoute(
          path: '/menu/:id',
          builder: (context, state) => MenuScreen(restaurantId: state.pathParameters['id']!),
        ),
        GoRoute(path: '/carrito', builder: (context, state) => const CartScreen()),
        GoRoute(path: '/pedidos', builder: (context, state) => const OrderHistoryScreen()),
      ],
    );
    return MaterialApp.router(
      title: 'MyDeliveryS',
      theme: appTheme(),
      routerConfig: router,
    );
  }
}

class CustomerHome extends ConsumerWidget {
  const CustomerHome({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
        appBar: AppBar(
          title: const Text('MyDeliveryS'),
          actions: [
            IconButton(
              tooltip: 'Mis pedidos',
              onPressed: () => context.go('/pedidos'),
              icon: const Icon(Icons.receipt_long_outlined),
            ),
            Badge(
              label: Text('${ref.watch(cartControllerProvider).count}'),
              child: IconButton(
                tooltip: 'Carrito',
                onPressed: () => context.go('/carrito'),
                icon: const Icon(Icons.shopping_bag_outlined),
              ),
            ),
          ],
        ),
        body: FutureBuilder<List<Map<String, dynamic>>>(
          future: ref.read(deliveryRepositoryProvider).restaurants(),
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
            final restaurants = snapshot.data ?? [];
            if (restaurants.isEmpty) {
              return const Center(child: Text('No hay restaurantes abiertos ahora.'));
            }
            return RefreshIndicator(
              onRefresh: () async =>
                  (context as Element).markNeedsBuild(),
              child: ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: restaurants.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final restaurant = restaurants[index];
                  return Card(
                    child: ListTile(
                      contentPadding: const EdgeInsets.all(16),
                      leading: const CircleAvatar(child: Icon(Icons.restaurant)),
                      title: Text(restaurant['name'] as String? ?? 'Restaurante'),
                      subtitle: Text(restaurant['address'] as String? ?? 'San Juan de los Morros'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.go('/menu/${restaurant['id']}'),
                    ),
                  );
                },
              ),
            );
          },
        ),
      );
}

class MenuScreen extends ConsumerWidget {
  const MenuScreen({super.key, required this.restaurantId});
  final String restaurantId;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
        appBar: AppBar(title: const Text('Menu')),
        body: FutureBuilder<Map<String, dynamic>>(
          future: ref.read(deliveryRepositoryProvider).menu(restaurantId),
          builder: (context, snapshot) {
            if (!snapshot.hasData) {
              if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
              return const Center(child: CircularProgressIndicator());
            }
            final menu = snapshot.data!;
            final products = (menu['products'] as List? ?? const []);
            return ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: products.length,
              itemBuilder: (context, index) {
                final product = Map<String, dynamic>.from(products[index] as Map);
                final available = product['is_available'] == true;
                return Card(
                  child: ListTile(
                    contentPadding: const EdgeInsets.all(16),
                    title: Text(product['name'] as String),
                    subtitle: Text(product['description'] as String? ?? ''),
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text('\$${product['base_price']}', style: moneyStyle),
                        const SizedBox(height: 4),
                        IconButton(
                          tooltip: available ? 'Agregar al carrito' : 'No disponible',
                          onPressed: !available
                              ? null
                              : () {
                                  final item = CartItem(
                                    productId: product['id'] as String,
                                    restaurantId: restaurantId,
                                    name: product['name'] as String,
                                  );
                                  final controller = ref.read(cartControllerProvider.notifier);
                                  final result = controller.add(
                                    item,
                                    restaurantName: menu['restaurant_name'] as String?,
                                  );
                                  if (result == CartAddResult.conflict) {
                                    _confirmReplace(context, controller, item,
                                        menu['restaurant_name'] as String?);
                                  }
                                },
                          icon: const Icon(Icons.add_circle_outline),
                        ),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        ),
      );

  Future<void> _confirmReplace(
    BuildContext context,
    CartController controller,
    CartItem item,
    String? restaurantName,
  ) async {
    final replace = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cambiar de restaurante'),
        content: const Text('Se vaciara el carrito actual para agregar este producto.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cambiar')),
        ],
      ),
    );
    if (replace == true) {
      controller.add(item, restaurantName: restaurantName, confirmedReplace: true);
    }
  }
}

class CartScreen extends ConsumerStatefulWidget {
  const CartScreen({super.key});
  @override
  ConsumerState<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends ConsumerState<CartScreen> {
  bool loading = false;

  Future<void> quote() async {
    setState(() => loading = true);
    try {
      final repository = ref.read(deliveryRepositoryProvider);
      final addresses = await repository.addresses();
      if (addresses.isEmpty) throw StateError('Agrega una direccion antes de cotizar.');
      final order = await repository.createDraft(
        ref.read(cartControllerProvider).items,
        addresses.first['id'] as String,
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Cotizacion reservada por 15 minutos'),
          content: Text(
            'Total: \$${order['total_amount']}\nPrimer pago: \$${order['payment_breakdown']['first_half']}\nSegundo pago: \$${order['payment_breakdown']['second_half']}',
            style: moneyStyle,
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Entendido'))],
        ),
      );
    } catch (cause) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$cause')));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Tu carrito')),
      body: cart.isEmpty
          ? const Center(child: Text('Tu carrito esta vacio.'))
          : ListView.builder(
              itemCount: cart.items.length,
              itemBuilder: (context, index) => ListTile(
                title: Text(cart.items[index].name),
                subtitle: Text('Cantidad ${cart.items[index].quantity}'),
                trailing: IconButton(
                  tooltip: 'Quitar',
                  onPressed: () => ref.read(cartControllerProvider.notifier).removeAt(index),
                  icon: const Icon(Icons.delete_outline),
                ),
              ),
            ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.all(16),
        child: FilledButton(
          onPressed: cart.isEmpty || loading ? null : quote,
          child: Text(loading ? 'Cotizando...' : 'Cotizar con el servidor'),
        ),
      ),
    );
  }
}

class OrderHistoryScreen extends ConsumerWidget {
  const OrderHistoryScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
        appBar: AppBar(title: const Text('Mis pedidos')),
        body: FutureBuilder<List<Map<String, dynamic>>>(
          future: ref.read(deliveryRepositoryProvider).orders(),
          builder: (context, snapshot) {
            if (!snapshot.hasData) {
              if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
              return const Center(child: CircularProgressIndicator());
            }
            return ListView(
              children: [
                for (final order in snapshot.data!)
                  ListTile(
                    title: Text(order['order_number'] as String),
                    subtitle: Text(order['status'] as String),
                    trailing: Text('\$${order['total_amount']}', style: moneyStyle),
                  ),
              ],
            );
          },
        ),
      );
}
