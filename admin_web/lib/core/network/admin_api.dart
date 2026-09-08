import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

import 'http_client_factory.dart';

class AdminApi {
  AdminApi({
    required this.readCsrf,
    required this.onUnauthenticated,
    http.Client? client,
    String? baseUrl,
  })  : _client = client ?? createHttpClient(),
        _baseUrl = baseUrl ??
            const String.fromEnvironment(
              'API_BASE_URL',
              defaultValue: 'http://localhost:8000/api/v1',
            );

  final http.Client _client;
  final String _baseUrl;
  final String? Function() readCsrf;
  final Future<void> Function() onUnauthenticated;

  Future<Object?> _request(
    String method,
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
    Map<String, String>? query,
  }) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    final allHeaders = <String, String>{
      'Content-Type': 'application/json',
      ...?headers,
    };
    if (method != 'GET') {
      allHeaders['X-Idempotency-Key'] = const Uuid().v4();
      final csrf = readCsrf();
      if (csrf != null) allHeaders['X-CSRF-Token'] = csrf;
    }
    final response = await switch (method) {
      'GET' => _client.get(uri, headers: allHeaders),
      _ => _client.post(uri, headers: allHeaders, body: jsonEncode(body ?? {})),
    };
    if (response.statusCode == 401) await onUnauthenticated();
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const AdminApiError(
          'INVALID_RESPONSE', 'Respuesta invalida del servidor.');
    }
    if (decoded['success'] != true) {
      throw AdminApiError(
        decoded['error_code'] as String?,
        decoded['message'] as String? ?? 'Error de operacion.',
      );
    }
    return decoded['data'];
  }

  Future<Map<String, dynamic>> login(
          String identifier, String password) async =>
      Map<String, dynamic>.from(
        await _request(
          'POST',
          '/auth/web/login',
          body: {'phone': identifier, 'password': password},
        ) as Map,
      );

  Future<Map<String, dynamic>> verify2fa(
          String pendingToken, String code) async =>
      Map<String, dynamic>.from(
        await _request(
          'POST',
          '/auth/web/2fa/verify',
          body: {'code': code},
          headers: {'X-Pending-Token': pendingToken},
        ) as Map,
      );

  Future<List<dynamic>> pendingPayments() async => List<dynamic>.from(
      await _request('GET', '/admin/payments/pending') as List);

  Future<Map<String, dynamic>> verifyPayment(String paymentId) async =>
      Map<String, dynamic>.from(
        await _request('POST', '/admin/payments/$paymentId/verify') as Map,
      );

  Future<Map<String, dynamic>> rejectPayment(
          String paymentId, String reason) async =>
      Map<String, dynamic>.from(
        await _request(
          'POST',
          '/admin/payments/$paymentId/reject',
          body: {'reason': reason},
        ) as Map,
      );

  Future<Map<String, dynamic>> rateHealth() async => Map<String, dynamic>.from(
        await _request('GET', '/admin/exchange-rate/health') as Map,
      );

  Future<Map<String, dynamic>> kanban(String restaurantId) async =>
      Map<String, dynamic>.from(
        await _request(
          'GET',
          '/restaurant/kanban',
          query: {'restaurant_id': restaurantId},
        ) as Map,
      );

  Future<List<dynamic>> readyList(String restaurantId) async =>
      List<dynamic>.from(
        await _request(
          'GET',
          '/restaurant/ready-list',
          query: {'restaurant_id': restaurantId},
        ) as List,
      );

  Future<Map<String, dynamic>> acknowledge(String orderId) async =>
      Map<String, dynamic>.from(
        await _request('POST', '/restaurant/orders/$orderId/acknowledge')
            as Map,
      );

  Future<Map<String, dynamic>> markReady(String orderId) async =>
      Map<String, dynamic>.from(
        await _request('POST', '/restaurant/orders/$orderId/ready') as Map,
      );

  Future<Map<String, dynamic>> createRefund(Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(
        await _request('POST', '/admin/refunds', body: body) as Map,
      );

  Future<Map<String, dynamic>> createSettlement(
          Map<String, dynamic> body) async =>
      Map<String, dynamic>.from(
        await _request('POST', '/admin/settlements', body: body) as Map,
      );
}

class AdminApiError implements Exception {
  const AdminApiError(this.code, this.message);
  final String? code;
  final String message;
  @override
  String toString() => message;
}
