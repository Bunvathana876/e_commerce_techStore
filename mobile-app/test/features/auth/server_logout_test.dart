import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/features/auth/models/user_model.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_api_service.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const oldUser = UserModel(
    id: 1,
    email: 'a@example.invalid',
    fullName: 'A',
    role: 'customer',
  );
  const newUser = UserModel(
    id: 2,
    email: 'b@example.invalid',
    fullName: 'B',
    role: 'customer',
  );

  setUp(() {
    AuthProvider.clearLogoutListeners();
    ApiClient.instance.clearAuthToken();
    ApiClient.instance.onUnauthorized = null;
    ApiClient.globalOnUnauthorized = null;
  });
  tearDown(() {
    AuthProvider.clearLogoutListeners();
    ApiClient.instance.clearAuthToken();
    ApiClient.instance.onUnauthorized = null;
    ApiClient.globalOnUnauthorized = null;
  });

  for (final outcome in [200, 401, 500, 'offline']) {
    test(
      'logout sends captured bearer and clears session for $outcome',
      () async {
        SharedPreferences.setMockInitialValues({
          'auth_token': 'fixture-old-token',
          'auth_user': jsonEncode(oldUser.toJson()),
          'user_orders_cache': 'private',
          'app_theme_mode': 'dark',
        });
        final prefs = await SharedPreferences.getInstance();
        var requests = 0;
        final client = ApiClient(
          client: MockClient((request) async {
            requests++;
            expect(request.url.path, '/api/v1/auth/logout');
            expect(request.method, 'POST');
            expect(
              request.headers['Authorization'],
              'Bearer fixture-old-token',
            );
            if (outcome == 'offline') {
              throw http.ClientException('fixture-private-error');
            }
            return http.Response('{}', outcome as int);
          }),
        );
        final provider = AuthProvider(
          initialPrefs: prefs,
          authService: AuthService(apiService: AuthApiService(client: client)),
        );
        var cleaned = 0;
        AuthProvider.registerLogoutListener(() {
          cleaned++;
        });
        final pending = provider.logout();
        expect(provider.isAuthenticated, isFalse);
        expect(ApiClient.instance.authToken, isNull);
        await pending;
        expect(requests, 1);
        expect(cleaned, 1);
        expect(prefs.getString('auth_token'), isNull);
        expect(prefs.getString('auth_user'), isNull);
        expect(prefs.getString('user_orders_cache'), isNull);
        expect(prefs.getString('app_theme_mode'), 'dark');
        provider.dispose();
        client.dispose();
      },
    );
  }

  for (final status in [200, 401]) {
    test('delayed logout $status cannot erase a newer login', () async {
      SharedPreferences.setMockInitialValues({
        'auth_token': 'fixture-old-token',
        'auth_user': jsonEncode(oldUser.toJson()),
      });
      final prefs = await SharedPreferences.getInstance();
      final response = Completer<http.Response>();
      final client = ApiClient(
        client: MockClient((request) => response.future),
      );
      final provider = AuthProvider(
        initialPrefs: prefs,
        authService: AuthService(apiService: AuthApiService(client: client)),
      );
      final localCleanup = Completer<void>();
      provider.addListener(() {
        if (!provider.isAuthenticated && !localCleanup.isCompleted) {
          localCleanup.complete();
        }
      });
      final pending = provider.logout();
      await localCleanup.future;
      await provider.saveUserSession(token: 'fixture-new-token', user: newUser);
      response.complete(http.Response('{}', status));
      await pending;
      expect(provider.currentUser?.id, 2);
      expect(provider.token, 'fixture-new-token');
      expect(ApiClient.instance.authToken, 'fixture-new-token');
      expect(prefs.getString('auth_token'), 'fixture-new-token');
      provider.dispose();
      client.dispose();
    });
  }

  test('late protected-request 401 cannot invalidate a newer bearer', () async {
    final response = Completer<http.Response>();
    final client = ApiClient(client: MockClient((request) => response.future));
    var unauthorized = 0;
    client.onUnauthorized = () {
      unauthorized++;
    };
    client.setAuthToken('fixture-old-token');
    final pending = client.get<dynamic>('/api/v1/auth/me');
    final assertion = expectLater(pending, throwsException);
    client.setAuthToken('fixture-new-token');
    response.complete(http.Response('{}', 401));
    await assertion;
    expect(unauthorized, 0);
    expect(client.authToken, 'fixture-new-token');
    client.dispose();
  });
  test(
    'logout and corrupt-session errors never log credential values',
    () async {
      final messages = <String>[];
      final originalDebugPrint = debugPrint;
      debugPrint = (String? message, {int? wrapWidth}) {
        if (message != null) messages.add(message);
      };
      try {
        SharedPreferences.setMockInitialValues({
          'auth_token': 'fixture-secret-token',
          'auth_user': '{fixture-secret-token invalid-json',
        });
        var prefs = await SharedPreferences.getInstance();
        final corruptProvider = AuthProvider(initialPrefs: prefs);
        expect(corruptProvider.isAuthenticated, isFalse);
        corruptProvider.dispose();
        SharedPreferences.setMockInitialValues({
          'auth_token': 'fixture-secret-token',
          'auth_user': jsonEncode(oldUser.toJson()),
        });
        prefs = await SharedPreferences.getInstance();
        final client = ApiClient(
          client: MockClient((request) async {
            throw http.ClientException('fixture-secret-token');
          }),
        );
        final provider = AuthProvider(
          initialPrefs: prefs,
          authService: AuthService(apiService: AuthApiService(client: client)),
        );
        AuthProvider.registerLogoutListener(() {
          throw StateError('fixture-secret-token');
        });
        await provider.logout();
        expect(messages, isNotEmpty);
        expect(messages.join(), isNot(contains('fixture-secret-token')));
        provider.dispose();
        client.dispose();
      } finally {
        debugPrint = originalDebugPrint;
      }
    },
  );
}
