import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/config/app_colors.dart';
import 'core/config/console_kind.dart';
import 'core/network/admin_api.dart';
import 'features/auth/login_screen.dart';
import 'features/kanban/kanban_screen.dart';
import 'features/ops/ops_screens.dart';
import 'features/reconciliation/reconciliation_screen.dart';

class ConsoleApp extends ConsumerWidget {
  const ConsoleApp({super.key, required this.kind});
  final ConsoleKind kind;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final home = kind == ConsoleKind.admin ? '/conciliacion' : '/kanban';
    final authenticated = ref.watch(sessionProvider)['authenticated'] == 'true';
    final router = GoRouter(
      initialLocation: authenticated ? home : '/login',
      routes: [
        GoRoute(
          path: '/login',
          builder: (context, state) => LoginScreen(homePath: home, kind: kind),
        ),
        ShellRoute(
          builder: (context, state, child) =>
              ConsoleShell(kind: kind, child: child),
          routes: [
            GoRoute(
                path: '/conciliacion',
                builder: (_, __) => const ReconciliationScreen()),
            GoRoute(path: '/kanban', builder: (_, __) => const KanbanScreen()),
            GoRoute(
                path: '/tasa', builder: (_, __) => const RateHealthScreen()),
            GoRoute(
                path: '/liquidaciones',
                builder: (_, __) => const SettlementsScreen()),
            GoRoute(
                path: '/mapa', builder: (_, __) => const OperationsMapScreen()),
          ],
        ),
      ],
    );
    return ProviderScope(
      overrides: [
        adminApiProvider.overrideWith(
          (ref) => AdminApi(
            readCsrf: () => ref.read(sessionProvider)['csrf'],
            onUnauthenticated: () async {
              ref.read(sessionProvider.notifier).state = const {};
            },
          ),
        ),
      ],
      child: MaterialApp.router(
        title: kind == ConsoleKind.admin
            ? 'MyDeliveryS Administracion'
            : 'MyDeliveryS Restaurante',
        theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: AppColors.background,
          colorScheme: ColorScheme.fromSeed(seedColor: AppColors.primary500),
        ),
        routerConfig: router,
      ),
    );
  }
}

class ConsoleShell extends StatelessWidget {
  const ConsoleShell({super.key, required this.kind, required this.child});
  final ConsoleKind kind;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final items = kind == ConsoleKind.admin
        ? const [
            ('/conciliacion', 'Conciliacion', Icons.fact_check_outlined),
            ('/tasa', 'Tasa', Icons.currency_exchange),
            (
              '/liquidaciones',
              'Liquidaciones',
              Icons.account_balance_wallet_outlined
            ),
            ('/mapa', 'Mapa', Icons.map_outlined),
          ]
        : const [('/kanban', 'Pedidos', Icons.view_kanban_outlined)];
    final path = GoRouterState.of(context).matchedLocation;
    final selected =
        items.indexWhere((item) => item.$1 == path).clamp(0, items.length - 1);
    return Scaffold(
      appBar: AppBar(
        title: Text(kind == ConsoleKind.admin
            ? 'Administracion MyDeliveryS'
            : 'Panel del restaurante'),
      ),
      body: Row(
        children: [
          NavigationRail(
            labelType: NavigationRailLabelType.all,
            destinations: [
              for (final item in items)
                NavigationRailDestination(
                    icon: Icon(item.$3), label: Text(item.$2)),
            ],
            selectedIndex: selected,
            onDestinationSelected: (index) => context.go(items[index].$1),
          ),
          const VerticalDivider(width: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}
