import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import 'app_theme.dart';
import 'core/providers.dart';
import 'features/auth/presentation/auth_screen.dart';
import 'features/driver/data/driver_repository.dart';

final driverRepositoryProvider = Provider<DriverRepository>(
  (ref) => DriverRepository(ref.watch(apiClientProvider)),
);
final solarModeProvider = StateProvider<bool>((ref) => false);

class DriverApp extends ConsumerWidget {
  const DriverApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loggedIn = ref.watch(accessTokenProvider) != null;
    final solar = ref.watch(solarModeProvider);
    final router = GoRouter(
      initialLocation: loggedIn ? '/' : '/acceso',
      routes: [
        GoRoute(
          path: '/acceso',
          builder: (context, state) => AuthScreen(
            partner: true,
            onAuthenticated: () => context.go('/'),
          ),
        ),
        GoRoute(path: '/', builder: (context, state) => const DriverHome()),
        GoRoute(
          path: '/pedido/:id',
          builder: (context, state) => ActiveDeliveryScreen(orderId: state.pathParameters['id']!),
        ),
      ],
    );
    return MaterialApp.router(
      title: 'MyDeliveryS Conductor',
      theme: appTheme(solar: solar),
      routerConfig: router,
    );
  }
}

class DriverHome extends ConsumerStatefulWidget {
  const DriverHome({super.key});
  @override
  ConsumerState<DriverHome> createState() => _DriverHomeState();
}

class _DriverHomeState extends ConsumerState<DriverHome> {
  bool available = false;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Conductor'),
          actions: [
            IconButton(
              tooltip: 'Modo solar',
              onPressed: () {
                final current = ref.read(solarModeProvider);
                ref.read(solarModeProvider.notifier).state = !current;
              },
              icon: const Icon(Icons.wb_sunny_outlined),
            ),
          ],
        ),
        body: Column(
          children: [
            SwitchListTile(
              title: Text(available ? 'Disponible para entregas' : 'No disponible'),
              value: available,
              onChanged: (value) async {
                await ref.read(driverRepositoryProvider).setAvailable(value);
                if (mounted) setState(() => available = value);
              },
            ),
            Expanded(
              child: FutureBuilder<List<Map<String, dynamic>>>(
                future: ref.read(driverRepositoryProvider).availableOrders(),
                builder: (context, snapshot) {
                  if (!snapshot.hasData) {
                    if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
                    return const Center(child: CircularProgressIndicator());
                  }
                  final orders = snapshot.data!;
                  if (orders.isEmpty) return const Center(child: Text('Sin pedidos disponibles.'));
                  return ListView.builder(
                    itemCount: orders.length,
                    itemBuilder: (context, index) {
                      final order = orders[index];
                      return Card(
                        child: ListTile(
                          title: Text(order['order_number'] as String),
                          trailing: FilledButton(
                            onPressed: () async {
                              await ref.read(driverRepositoryProvider).action(
                                    order['id'] as String,
                                    'accept',
                                  );
                              if (context.mounted) context.go('/pedido/${order['id']}');
                            },
                            child: const Text('Aceptar'),
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      );
}

class ActiveDeliveryScreen extends ConsumerStatefulWidget {
  const ActiveDeliveryScreen({super.key, required this.orderId});
  final String orderId;
  @override
  ConsumerState<ActiveDeliveryScreen> createState() => _ActiveDeliveryScreenState();
}

class _ActiveDeliveryScreenState extends ConsumerState<ActiveDeliveryScreen> {
  String status = 'READY_FOR_PICKUP';
  String? message;

  Future<void> action(String action, String next) async {
    try {
      await ref.read(driverRepositoryProvider).action(widget.orderId, action);
      setState(() {
        status = next;
        message = null;
      });
    } catch (cause) {
      setState(() => message = '$cause');
    }
  }

  Future<void> sendLocation() async {
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      setState(() => message = 'Activa el permiso de ubicacion para continuar.');
      return;
    }
    final position = await Geolocator.getCurrentPosition();
    await ref.read(driverRepositoryProvider).publishLocation(
          widget.orderId,
          position.latitude.toString(),
          position.longitude.toString(),
          position.heading.toString(),
        );
    setState(() => message = 'Ubicacion enviada.');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text('Pedido ${widget.orderId.substring(0, 8)}')),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Semantics(
              liveRegion: true,
              child: Text(status, style: Theme.of(context).textTheme.headlineSmall),
            ),
            const SizedBox(height: 20),
            if (status == 'READY_FOR_PICKUP')
              FilledButton(
                onPressed: () => action('pickup', 'ON_THE_WAY'),
                child: const Text('Confirmar recogida'),
              ),
            if (status == 'ON_THE_WAY') ...[
              OutlinedButton.icon(
                onPressed: sendLocation,
                icon: const Icon(Icons.my_location),
                label: const Text('Enviar ubicacion actual'),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () => action('arrived', 'ARRIVED_AT_CUSTOMER'),
                child: const Text('Llegue al cliente'),
              ),
            ],
            if (status == 'ARRIVED_AT_CUSTOMER') ...[
              FilledButton(
                onPressed: () => _cashDialog(context),
                child: const Text('Confirmar efectivo y entrega'),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => _digitalDialog(context),
                child: const Text('Reportar Pago Movil'),
              ),
            ],
            if (status == 'PAYMENT_2_VERIFYING')
              FilledButton(
                onPressed: () => action('complete-delivery', 'DELIVERED'),
                child: const Text('Confirmar entrega fisica'),
              ),
            if (message != null) ...[
              const SizedBox(height: 16),
              Text(message!, semanticsLabel: message),
            ],
          ],
        ),
      );

  Future<void> _cashDialog(BuildContext context) async {
    final usd = TextEditingController();
    final ves = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Efectivo recibido'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: usd, decoration: const InputDecoration(labelText: 'USD')),
            TextField(controller: ves, decoration: const InputDecoration(labelText: 'VES opcional')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Confirmar')),
        ],
      ),
    );
    if (accepted == true) {
      await ref.read(driverRepositoryProvider).collectCash(
            widget.orderId,
            amountUsd: usd.text.trim().isEmpty ? '0.00' : usd.text.trim(),
            amountVes: ves.text.trim(),
          );
      setState(() => status = 'DELIVERED');
    }
    usd.dispose();
    ves.dispose();
  }

  Future<void> _digitalDialog(BuildContext context) async {
    final reference = TextEditingController();
    final bank = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reportar Pago Movil'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: reference, decoration: const InputDecoration(labelText: 'Referencia')),
            TextField(controller: bank, decoration: const InputDecoration(labelText: 'Banco')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Enviar')),
        ],
      ),
    );
    if (accepted == true) {
      await ref.read(driverRepositoryProvider).reportDigital(
            widget.orderId,
            reference: reference.text.trim(),
            bank: bank.text.trim(),
          );
      setState(() => status = 'PAYMENT_2_VERIFYING');
    }
    reference.dispose();
    bank.dispose();
  }
}
