import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/auth_repository.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key, required this.partner, required this.onAuthenticated});
  final bool partner;
  final VoidCallback onAuthenticated;

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  final phone = TextEditingController();
  final secret = TextEditingController();
  bool otpRequested = false;
  bool loading = false;
  String? error;

  Future<void> submit() async {
    setState(() {
      loading = true;
      error = null;
    });
    final repository = AuthRepository(
      ref.read(apiClientProvider),
      ref.read(sessionStoreProvider),
    );
    try {
      if (widget.partner) {
        await repository.loginPartner(phone.text.trim(), secret.text);
      } else if (!otpRequested) {
        await repository.requestOtp(phone.text.trim());
        if (mounted) setState(() => otpRequested = true);
        return;
      } else {
        await repository.verifyOtp(phone.text.trim(), secret.text.trim());
      }
      final token = await ref.read(sessionStoreProvider).readAccessToken();
      ref.read(accessTokenProvider.notifier).state = token;
      widget.onAuthenticated();
    } catch (cause) {
      if (mounted) setState(() => error = cause.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      widget.partner ? 'Acceso de conductor' : 'Pide lo que te gusta',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 24),
                    TextField(
                      controller: phone,
                      keyboardType: widget.partner ? TextInputType.text : TextInputType.phone,
                      decoration: InputDecoration(
                        labelText: widget.partner ? 'Telefono' : 'Telefono venezolano',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                    if (widget.partner || otpRequested) ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: secret,
                        obscureText: widget.partner,
                        keyboardType:
                            widget.partner ? TextInputType.text : TextInputType.number,
                        decoration: InputDecoration(
                          labelText: widget.partner ? 'Contrasena' : 'Codigo de 6 digitos',
                          border: const OutlineInputBorder(),
                        ),
                      ),
                    ],
                    if (error != null) ...[
                      const SizedBox(height: 12),
                      Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ],
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: loading ? null : submit,
                      child: Text(
                        loading
                            ? 'Procesando...'
                            : widget.partner
                                ? 'Entrar'
                                : otpRequested
                                    ? 'Verificar codigo'
                                    : 'Enviar codigo por WhatsApp',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );

  @override
  void dispose() {
    phone.dispose();
    secret.dispose();
    super.dispose();
  }
}
