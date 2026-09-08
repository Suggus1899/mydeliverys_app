import '../../../core/network/api_client.dart';
import '../../../core/storage/session_store.dart';

class AuthRepository {
  const AuthRepository(this._api, this._store);
  final ApiClient _api;
  final SessionStore _store;

  Future<void> requestOtp(String phone) =>
      _api.post('/auth/request-otp', (_) {}, body: {'phone': phone});

  Future<bool> verifyOtp(String phone, String otp) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/auth/verify-otp',
      (raw) => Map<String, dynamic>.from(raw! as Map),
      body: {'phone': phone, 'otp': otp},
    );
    await _store.saveTokens(
      data['access_token'] as String,
      data['refresh_token'] as String,
    );
    return data['is_new'] == true;
  }

  Future<void> loginPartner(String phone, String password) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/auth/login',
      (raw) => Map<String, dynamic>.from(raw! as Map),
      body: {'phone': phone, 'password': password},
    );
    await _store.saveTokens(
      data['access_token'] as String,
      data['refresh_token'] as String,
    );
  }
}
