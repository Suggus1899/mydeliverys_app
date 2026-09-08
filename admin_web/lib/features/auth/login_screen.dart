import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/app_colors.dart';
import '../../core/config/console_kind.dart';
import '../reconciliation/reconciliation_screen.dart';

final sessionProvider = StateProvider<Map<String, String?>>((ref) => const {});

/// Login web con cookie HttpOnly. Super Admin exige un segundo paso TOTP.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, required this.homePath, required this.kind});
  final String homePath;
  final ConsoleKind kind;
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final phone = TextEditingController();
  final password = TextEditingController();
  final code = TextEditingController();
  bool requires2fa = false;
  bool loading = false;
  String? pendingToken;
  String? error;

  bool _acceptsRole(String? role) => widget.kind == ConsoleKind.admin
      ? role == 'SUPER_ADMIN'
      : role == 'RESTAURANT';

  Future<void> _login() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final api = ref.read(adminApiProvider);
      final data = await api.login(phone.text.trim(), password.text);
      if (data['requires_2fa'] == true) {
        if (widget.kind != ConsoleKind.admin) {
          throw StateError('Esta cuenta no tiene acceso a esta consola.');
        }
        setState(() {
          requires2fa = true;
          pendingToken = data['pending_token'] as String?;
        });
        return;
      }
      if (!_acceptsRole(data['role'] as String?)) {
        throw StateError('Esta cuenta no tiene acceso a esta consola.');
      }
      ref.read(sessionProvider.notifier).state = {
        'authenticated': 'true',
        'csrf': data['csrf_token'] as String?,
        'role': data['role'] as String?,
        'restaurant_id': data['restaurant_id'] as String?,
      };
      if (mounted) context.go(widget.homePath);
    } catch (cause) {
      if (mounted) setState(() => error = cause.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _verify2fa() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final api = ref.read(adminApiProvider);
      final data = await api.verify2fa(pendingToken!, code.text.trim());
      ref.read(sessionProvider.notifier).state = {
        'authenticated': 'true',
        'csrf': data['csrf_token'] as String?,
        'role': 'SUPER_ADMIN',
      };
      if (mounted) context.go(widget.homePath);
    } catch (cause) {
      if (mounted) setState(() => error = cause.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Card(
            color: AppColors.surface,
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('MyDeliveryS Consola',
                      style:
                          TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  if (error != null) ...[
                    Text(error!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error)),
                    const SizedBox(height: 12),
                  ],
                  if (!requires2fa) ...[
                    TextField(
                        controller: phone,
                        decoration: const InputDecoration(
                            labelText: 'Telefono o email',
                            border: OutlineInputBorder())),
                    const SizedBox(height: 12),
                    TextField(
                        controller: password,
                        obscureText: true,
                        decoration: const InputDecoration(
                            labelText: 'Contrasena',
                            border: OutlineInputBorder())),
                    const SizedBox(height: 16),
                    ElevatedButton(
                        onPressed: loading ? null : _login,
                        style: ElevatedButton.styleFrom(
                            minimumSize: const Size.fromHeight(48)),
                        child: Text(loading ? 'Procesando...' : 'Entrar')),
                  ] else ...[
                    const Text('Super Admin: ingresa codigo 2FA'),
                    const SizedBox(height: 12),
                    TextField(
                        controller: code,
                        maxLength: 6,
                        decoration: const InputDecoration(
                            labelText: 'Codigo 6 digitos',
                            border: OutlineInputBorder())),
                    const SizedBox(height: 16),
                    ElevatedButton(
                        onPressed: loading ? null : _verify2fa,
                        style: ElevatedButton.styleFrom(
                            minimumSize: const Size.fromHeight(48)),
                        child:
                            Text(loading ? 'Verificando...' : 'Verificar 2FA')),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    phone.dispose();
    password.dispose();
    code.dispose();
    super.dispose();
  }
}
