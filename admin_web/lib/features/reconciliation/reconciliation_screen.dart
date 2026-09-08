import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/app_colors.dart';
import '../../core/network/admin_api.dart';

final adminApiProvider =
    Provider<AdminApi>((ref) => throw UnimplementedError('Proveer en main()'));

final pendingProvider = FutureProvider<List<dynamic>>((ref) async {
  return ref.watch(adminApiProvider).pendingPayments();
});

/// Bandeja de conciliacion: lista izquierda + comprobante derecha.
/// Atajos: [A] aprobar, [R] rechazar, flechas navegar. RF-ADM-08..12.
class ReconciliationScreen extends ConsumerStatefulWidget {
  const ReconciliationScreen({super.key});

  @override
  ConsumerState<ReconciliationScreen> createState() =>
      _ReconciliationScreenState();
}

class _ReconciliationScreenState extends ConsumerState<ReconciliationScreen> {
  int selected = 0;
  final rejectReason = TextEditingController();

  Future<void> _approve(String paymentId) async {
    final api = ref.read(adminApiProvider);
    await api.verifyPayment(paymentId);
    ref.invalidate(pendingProvider);
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Pago verificado')));
    }
  }

  Future<void> _reject(String paymentId) async {
    final reason = rejectReason.text.trim().isEmpty
        ? 'Referencia no coincide'
        : rejectReason.text.trim();
    final api = ref.read(adminApiProvider);
    await api.rejectPayment(paymentId, reason);
    ref.invalidate(pendingProvider);
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Pago rechazado')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final pending = ref.watch(pendingProvider);
    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.keyA): () {
          final list = pending.valueOrNull;
          if (list != null && list.isNotEmpty) {
            _approve(list[selected.clamp(0, list.length - 1)]['payment_id']
                as String);
          }
        },
        const SingleActivator(LogicalKeyboardKey.keyR): () {
          final list = pending.valueOrNull;
          if (list != null && list.isNotEmpty) {
            _reject(list[selected.clamp(0, list.length - 1)]['payment_id']
                as String);
          }
        },
        const SingleActivator(LogicalKeyboardKey.arrowDown): () =>
            setState(() => selected++),
        const SingleActivator(LogicalKeyboardKey.arrowUp): () =>
            setState(() => selected = (selected - 1).clamp(0, 9999)),
      },
      child: Focus(
        autofocus: true,
        child: pending.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Error: $e')),
          data: (list) {
            if (list.isEmpty) {
              return const Center(child: Text('Sin pagos pendientes'));
            }
            selected = selected.clamp(0, list.length - 1);
            final current = Map<String, dynamic>.from(list[selected] as Map);
            return Row(
              children: [
                Expanded(
                  flex: 5,
                  child: ListView.builder(
                    itemCount: list.length,
                    itemBuilder: (context, i) {
                      final p = Map<String, dynamic>.from(list[i] as Map);
                      return ListTile(
                        selected: i == selected,
                        selectedTileColor: AppColors.card,
                        title: Text('${p['order_number']} · ${p['phase']}',
                            style:
                                const TextStyle(color: AppColors.textPrimary)),
                        subtitle: Text(
                            '${p['method']} · USD ${p['amount_usd']} · ${p['origin_bank']} ${p['reference_number'] ?? ''}',
                            style: const TextStyle(
                                color: AppColors.textSecondary)),
                        trailing: Text('USD ${p['amount_usd']}',
                            style:
                                AppColors.money(15, color: AppColors.warning)),
                        onTap: () => setState(() => selected = i),
                      );
                    },
                  ),
                ),
                const VerticalDivider(width: 1, color: AppColors.border),
                Expanded(
                  flex: 7,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Orden ${current['order_number']}',
                            style: const TextStyle(
                                fontSize: 20, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Text('Monto USD ${current['amount_usd']}',
                            style:
                                AppColors.money(28, color: AppColors.warning)),
                        const SizedBox(height: 8),
                        Text(
                            'Comprobante: ${current['proof_image_url'] ?? 'sin imagen'}',
                            style: const TextStyle(
                                color: AppColors.textSecondary)),
                        const SizedBox(height: 12),
                        TextField(
                            controller: rejectReason,
                            decoration: const InputDecoration(
                                labelText: 'Motivo de rechazo',
                                border: OutlineInputBorder())),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            ElevatedButton(
                              onPressed: () =>
                                  _approve(current['payment_id'] as String),
                              style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.success,
                                  minimumSize: const Size(140, 48)),
                              child: const Text('[A] Aprobar'),
                            ),
                            const SizedBox(width: 12),
                            OutlinedButton(
                              onPressed: () =>
                                  _reject(current['payment_id'] as String),
                              style: OutlinedButton.styleFrom(
                                  foregroundColor: AppColors.danger,
                                  minimumSize: const Size(140, 48)),
                              child: const Text('[R] Rechazar'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  @override
  void dispose() {
    rejectReason.dispose();
    super.dispose();
  }
}
