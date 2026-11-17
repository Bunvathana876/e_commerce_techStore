import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_exceptions.dart';

class CheckoutAttempt {
  final String key;
  final Map<String, dynamic> request;
  final DateTime createdAt;

  CheckoutAttempt({
    required this.key,
    required this.request,
    required this.createdAt,
  });

  List<Map<String, dynamic>> get items => (request['items'] as List)
      .map((item) => Map<String, dynamic>.from(item as Map))
      .toList();

  // The server may prune completed records after 24 hours. Never automatically
  // resubmit an unresolved older request once replay protection may have expired.
  bool get canRetry =>
      DateTime.now().difference(createdAt) < const Duration(hours: 23);
}

class CheckoutAttemptStore {
  // Separate checkout screens must share one durable reservation in this isolate.
  static Future<void>? _writeInFlight;
  Future<T> _serialize<T>(Future<T> Function() operation) async {
    final previous = _writeInFlight;
    final gate = Completer<void>();
    _writeInFlight = gate.future;
    try {
      if (previous != null) await previous;
      return await operation();
    } finally {
      if (identical(_writeInFlight, gate.future)) _writeInFlight = null;
      gate.complete();
    }
  }

  final Future<SharedPreferences> Function() _preferences;
  CheckoutAttemptStore({Future<SharedPreferences> Function()? preferences})
    : _preferences = preferences ?? SharedPreferences.getInstance;

  String _storageKey(int userId) =>
      'checkout_pending_v1_${base64Url.encode(utf8.encode(ApiEndpoints.baseUrl))}_$userId';

  Future<CheckoutAttempt?> read(int userId) async {
    final prefs = await _preferences();
    final raw = prefs.getString(_storageKey(userId));
    if (raw == null) return null;
    try {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      final attempt = CheckoutAttempt(
        key: data['key'] as String,
        request: Map<String, dynamic>.from(data['request'] as Map),
        createdAt: DateTime.parse(data['created_at'] as String),
      );
      if (attempt.key.isEmpty || attempt.items.isEmpty) {
        throw const FormatException();
      }
      return attempt;
    } catch (_) {
      // Losing an unreadable retry key must not silently create a second order.
      throw const ApiException(
        'Your previous checkout could not be restored. Check your orders or contact support before ordering again.',
      );
    }
  }

  Future<CheckoutAttempt> prepare(int userId, Map<String, dynamic> request) =>
      _serialize(() => _prepare(userId, request));

  Future<CheckoutAttempt> _prepare(
    int userId,
    Map<String, dynamic> request,
  ) async {
    final existing = await read(userId);
    if (existing != null) return existing;
    final random = Random.secure();
    final attempt = CheckoutAttempt(
      key:
          'mob_${List.generate(24, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join()}',
      request: request,
      createdAt: DateTime.now(),
    );
    final prefs = await _preferences();
    final saved = await prefs.setString(
      _storageKey(userId),
      jsonEncode({
        'key': attempt.key,
        'request': request,
        'created_at': attempt.createdAt.toIso8601String(),
      }),
    );
    if (!saved) {
      throw const ApiException(
        'Unable to save checkout for safe retry. No order was sent. Please try again.',
      );
    }
    return attempt;
  }

  Future<void> complete(int userId, String key) =>
      _serialize(() => _complete(userId, key));

  Future<void> _complete(int userId, String key) async {
    final current = await read(userId);
    if (current?.key != key) return;
    final prefs = await _preferences();
    if (!await prefs.remove(_storageKey(userId))) {
      throw const ApiException(
        'Could not finish saving checkout confirmation. Retry to retrieve the same order.',
      );
    }
  }
}
