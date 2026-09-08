import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

class ApiClient {
  ApiClient({
    required this.readAccessToken,
    required this.onUnauthenticated,
    http.Client? client,
    String? baseUrl,
  })  : _client = client ?? http.Client(),
        _baseUrl = baseUrl ??
            const String.fromEnvironment(
              'API_BASE_URL',
              defaultValue: 'http://10.0.2.2:8000/api/v1',
            );

  final http.Client _client;
  final String _baseUrl;
  final Future<String?> Function() readAccessToken;
  final Future<void> Function() onUnauthenticated;

  Future<T> get<T>(String path, T Function(Object? data) parse) =>
      _request('GET', path, parse: parse);

  Future<T> post<T>(
    String path,
    T Function(Object? data) parse, {
    Map<String, Object?>? body,
    bool idempotent = false,
  }) =>
      _request('POST', path, parse: parse, body: body, idempotent: idempotent);

  Future<T> patch<T>(
    String path,
    T Function(Object? data) parse, {
    Map<String, Object?>? body,
    bool idempotent = false,
  }) =>
      _request('PATCH', path, parse: parse, body: body, idempotent: idempotent);

  Future<T> _request<T>(
    String method,
    String path, {
    required T Function(Object? data) parse,
    Map<String, Object?>? body,
    bool idempotent = false,
  }) async {
    final operationKey = idempotent ? const Uuid().v4() : null;
    Object? lastError;
    for (var attempt = 0; attempt < 3; attempt++) {
      try {
        final token = await readAccessToken();
        final headers = <String, String>{'Content-Type': 'application/json'};
        if (token != null) headers['Authorization'] = 'Bearer $token';
        if (operationKey != null) headers['X-Idempotency-Key'] = operationKey;
        final uri = Uri.parse('$_baseUrl$path');
        final response = await switch (method) {
          'GET' => _client.get(uri, headers: headers),
          'PATCH' => _client.patch(uri, headers: headers, body: jsonEncode(body ?? {})),
          _ => _client.post(uri, headers: headers, body: jsonEncode(body ?? {})),
        }.timeout(const Duration(seconds: 15));
        if (response.statusCode == 401) await onUnauthenticated();
        if (response.statusCode >= 500 && attempt < 2) {
          await Future<void>.delayed(Duration(milliseconds: 250 * (1 << attempt)));
          continue;
        }
        final decoded = jsonDecode(response.body);
        if (decoded is! Map<String, dynamic>) {
          throw const ApiError('INVALID_RESPONSE', 'Respuesta invalida del servidor.');
        }
        if (decoded['success'] != true) {
          throw ApiError(
            decoded['error_code'] as String?,
            decoded['message'] as String? ?? 'Ocurrio un error.',
          );
        }
        return parse(decoded['data']);
      } on ApiError {
        rethrow;
      } on TimeoutException catch (error) {
        lastError = error;
      } on http.ClientException catch (error) {
        lastError = error;
      }
      if (attempt < 2) {
        await Future<void>.delayed(Duration(milliseconds: 250 * (1 << attempt)));
      }
    }
    throw ApiError('NETWORK_UNAVAILABLE', 'Sin conexion. Intenta nuevamente.', lastError);
  }
}

class ApiError implements Exception {
  const ApiError(this.code, this.message, [this.cause]);
  final String? code;
  final String message;
  final Object? cause;

  @override
  String toString() => message;
}
