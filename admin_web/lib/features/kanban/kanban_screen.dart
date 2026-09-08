import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/app_colors.dart';
import '../auth/login_screen.dart';
import '../reconciliation/reconciliation_screen.dart';

final kanbanProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final id = ref.watch(sessionProvider)['restaurant_id'] ?? '';
  if (id.isEmpty) return {'nuevos': [], 'en_preparacion': []};
  final api = ref.watch(adminApiProvider);
  final data = await api.kanban(id);
  data['listos'] = await api.readyList(id);
  return data;
});

/// Kanban restaurante: Nuevos / En preparacion / Listos + Historial separado.
/// RF-ADM-01..07. Tablet landscape y web.
class KanbanScreen extends ConsumerWidget {
  const KanbanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final kanban = ref.watch(kanbanProvider);
    return kanban.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (data) {
        final nuevos = List<dynamic>.from(data['nuevos'] as List? ?? []);
        final enPrep =
            List<dynamic>.from(data['en_preparacion'] as List? ?? []);
        final listos = List<dynamic>.from(data['listos'] as List? ?? []);
        return Row(
          children: [
            _Column(
                title: 'Nuevos (${nuevos.length})',
                color: AppColors.warning,
                items: nuevos,
                actionLabel: 'Empezar',
                onAction: (id) async {
                  await ref.read(adminApiProvider).acknowledge(id);
                  ref.invalidate(kanbanProvider);
                }),
            _Column(
                title: 'En preparacion (${enPrep.length})',
                color: AppColors.info,
                items: enPrep,
                actionLabel: 'Comida lista',
                onAction: (id) async {
                  await ref.read(adminApiProvider).markReady(id);
                  ref.invalidate(kanbanProvider);
                }),
            _Column(
              title: 'Listos para recoger (${listos.length})',
              color: AppColors.success,
              items: listos,
              actionLabel: '',
              onAction: (_) async {},
            ),
          ],
        );
      },
    );
  }
}

class _Column extends StatelessWidget {
  final String title;
  final Color color;
  final List<dynamic> items;
  final String actionLabel;
  final Future<void> Function(String id) onAction;
  const _Column(
      {required this.title,
      required this.color,
      required this.items,
      required this.actionLabel,
      required this.onAction});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              color: AppColors.card,
              child: Text(title,
                  style: TextStyle(color: color, fontWeight: FontWeight.bold))),
          Expanded(
            child: ListView.builder(
              itemCount: items.length,
              itemBuilder: (context, i) {
                final o = Map<String, dynamic>.from(items[i] as Map);
                return Card(
                  color: AppColors.surface,
                  child: ListTile(
                    title: Text(o['order_number'] as String? ?? '',
                        style: const TextStyle(color: AppColors.textPrimary)),
                    subtitle: Text('Total ${o['total'] ?? ''}',
                        style: AppColors.money(14,
                            color: AppColors.textSecondary)),
                    trailing: actionLabel.isEmpty
                        ? const Icon(Icons.inventory_2_outlined,
                            semanticLabel: 'Esperando conductor')
                        : ElevatedButton(
                            onPressed: () => onAction(o['id'] as String),
                            style: ElevatedButton.styleFrom(
                                minimumSize: const Size(120, 56)),
                            child: Text(actionLabel),
                          ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
