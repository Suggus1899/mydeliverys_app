import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/config/app_colors.dart';
import '../reconciliation/reconciliation_screen.dart';

/// Salud de tasa DolarAPI: banner rojo si bloquea cotizaciones. RF-ADM-18/19.
class RateHealthScreen extends ConsumerWidget {
  const RateHealthScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return FutureBuilder<Map<String, dynamic>>(
      future: ref.watch(adminApiProvider).rateHealth(),
      builder: (context, snap) {
        if (!snap.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final data = snap.data!;
        final blocking = data['is_blocking_new_orders'] == true;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (blocking)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                    color: AppColors.dangerBg,
                    borderRadius: BorderRadius.circular(12)),
                child: const Text(
                    'Tasa obsoleta: nuevas cotizaciones bloqueadas.',
                    style: TextStyle(
                        color: AppColors.danger, fontWeight: FontWeight.bold)),
              ),
            const SizedBox(height: 12),
            Text('Ultima tasa: ${data['last_valid_rate'] ?? '—'}',
                style: AppColors.money(28)),
            Text('Consultada: ${data['last_valid_queried_at'] ?? '—'}',
                style: const TextStyle(color: AppColors.textSecondary)),
          ],
        );
      },
    );
  }
}

/// Liquidaciones y reembolsos manuales (formularios minimos). RF-ADM-21..23.
class SettlementsScreen extends ConsumerStatefulWidget {
  const SettlementsScreen({super.key});
  @override
  ConsumerState<SettlementsScreen> createState() => _SettlementsScreenState();
}

class _SettlementsScreenState extends ConsumerState<SettlementsScreen> {
  final entityId = TextEditingController();
  final start = TextEditingController(text: '2026-09-01');
  final end = TextEditingController(text: '2026-09-07');
  String entityType = 'RESTAURANT';
  String? result;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Nueva liquidacion',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        DropdownButton<String>(
          value: entityType,
          items: const [
            DropdownMenuItem(value: 'RESTAURANT', child: Text('Restaurante')),
            DropdownMenuItem(value: 'DRIVER', child: Text('Conductor'))
          ],
          onChanged: (v) => setState(() => entityType = v!),
        ),
        TextField(
            controller: entityId,
            decoration: const InputDecoration(
                labelText: 'ID entidad (UUID)', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(
            controller: start,
            decoration: const InputDecoration(
                labelText: 'Inicio YYYY-MM-DD', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(
            controller: end,
            decoration: const InputDecoration(
                labelText: 'Fin YYYY-MM-DD', border: OutlineInputBorder())),
        const SizedBox(height: 12),
        ElevatedButton(
          onPressed: () async {
            final data = await ref.read(adminApiProvider).createSettlement({
              'entity_type': entityType,
              'entity_id': entityId.text.trim(),
              'period_start': start.text.trim(),
              'period_end': end.text.trim(),
              'currency': 'USD',
            });
            setState(() =>
                result = 'Liquidacion ${data['id']} · neto ${data['net']}');
          },
          style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary500,
              minimumSize: const Size.fromHeight(48)),
          child: const Text('Generar liquidacion'),
        ),
        if (result != null) ...[const SizedBox(height: 12), Text(result!)],
      ],
    );
  }

  @override
  void dispose() {
    entityId.dispose();
    start.dispose();
    end.dispose();
    super.dispose();
  }
}

/// Vista operativa con posiciones reales recibidas por WS. La cartografia vial
/// se habilita al configurar una clave de mapas antes del piloto.
class OperationsMapScreen extends StatefulWidget {
  const OperationsMapScreen({super.key});

  @override
  State<OperationsMapScreen> createState() => _OperationsMapScreenState();
}

class _OperationsMapScreenState extends State<OperationsMapScreen> {
  WebSocketChannel? channel;
  final positions = <String, Map<String, dynamic>>{};
  String? connectionError;

  @override
  void initState() {
    super.initState();
    const url = String.fromEnvironment(
      'ADMIN_MAP_WS_URL',
      defaultValue: 'ws://localhost:8000/ws/admin/map',
    );
    channel = WebSocketChannel.connect(Uri.parse(url));
    channel!.stream.listen(
      (raw) {
        final data = jsonDecode(raw as String);
        if (data is Map<String, dynamic> &&
            data['order_id'] != null &&
            mounted) {
          setState(() => positions[data['order_id'] as String] = data);
        }
      },
      onError: (Object error) {
        if (mounted) {
          setState(
              () => connectionError = 'No se pudo conectar al mapa en vivo.');
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Operaciones en vivo · ${positions.length} conductores',
              style: Theme.of(context).textTheme.titleLarge),
          if (connectionError != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(connectionError!,
                  style: const TextStyle(color: AppColors.danger)),
            ),
          const SizedBox(height: 12),
          Expanded(
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xFFE8EEF1),
                border: Border.all(color: AppColors.border),
                borderRadius: BorderRadius.circular(12),
              ),
              child: positions.isEmpty
                  ? const Center(
                      child: Text('Esperando ubicaciones recientes...'))
                  : LayoutBuilder(
                      builder: (context, constraints) => Stack(
                        children: [
                          const Positioned.fill(
                              child: CustomPaint(painter: _MapGridPainter())),
                          for (final entry in positions.entries)
                            Positioned(
                              left: _x(entry.value, constraints.maxWidth),
                              top: _y(entry.value, constraints.maxHeight),
                              child: Tooltip(
                                message: 'Pedido ${entry.key.substring(0, 8)}',
                                child: const Icon(Icons.delivery_dining,
                                    color: AppColors.primary500, size: 32),
                              ),
                            ),
                        ],
                      ),
                    ),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Vista relativa de posiciones. La capa vial requiere GOOGLE_MAPS_API_KEY antes del piloto.',
            style: TextStyle(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  double _x(Map<String, dynamic> value, double width) {
    final lng = double.tryParse('${value['lng']}') ?? -67.35;
    return ((lng + 67.45) / .2 * (width - 32)).clamp(0, width - 32);
  }

  double _y(Map<String, dynamic> value, double height) {
    final lat = double.tryParse('${value['lat']}') ?? 9.91;
    return ((10.01 - lat) / .2 * (height - 32)).clamp(0, height - 32);
  }

  @override
  void dispose() {
    channel?.sink.close();
    super.dispose();
  }
}

class _MapGridPainter extends CustomPainter {
  const _MapGridPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFCBD8DD)
      ..strokeWidth = 1;
    for (var i = 1; i < 8; i++) {
      canvas.drawLine(Offset(size.width * i / 8, 0),
          Offset(size.width * i / 8, size.height), paint);
      canvas.drawLine(Offset(0, size.height * i / 8),
          Offset(size.width, size.height * i / 8), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
