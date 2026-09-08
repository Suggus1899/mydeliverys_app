import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'core/providers.dart';
import 'core/storage/session_store.dart';
import 'features/cart/cart_controller.dart';

Future<void> bootstrap(Widget app) async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();
  final cartBox = await Hive.openBox<dynamic>('cart');
  const secureStorage = FlutterSecureStorage();
  const sessionStore = SessionStore(secureStorage);
  final token = await sessionStore.readAccessToken();
  runApp(
    ProviderScope(
      overrides: [
        sessionStoreProvider.overrideWithValue(sessionStore),
        accessTokenProvider.overrideWith((ref) => token),
        cartControllerProvider.overrideWith((ref) => CartController(cartBox)),
      ],
      child: app,
    ),
  );
}
