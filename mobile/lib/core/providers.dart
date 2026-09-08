import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'network/api_client.dart';
import 'storage/session_store.dart';

final sessionStoreProvider = Provider<SessionStore>(
  (ref) => const SessionStore(FlutterSecureStorage()),
);

final accessTokenProvider = StateProvider<String?>((ref) => null);

final apiClientProvider = Provider<ApiClient>((ref) {
  final store = ref.watch(sessionStoreProvider);
  return ApiClient(
    readAccessToken: store.readAccessToken,
    onUnauthenticated: () async {
      await store.clear();
      ref.read(accessTokenProvider.notifier).state = null;
    },
  );
});
