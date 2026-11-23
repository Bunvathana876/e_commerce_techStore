import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/auth/screens/forgot_password_screen.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_api_service.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('Account Recovery Flow Tests', () {
    testWidgets('requests reset link via API and confirms new password with token', (
      WidgetTester tester,
    ) async {
      final calls = <Map<String, dynamic>>[];
      final mockClient = ApiClient(
        client: MockClient((request) async {
          final body = request.body.isNotEmpty
              ? jsonDecode(request.body) as Map<String, dynamic>
              : <String, dynamic>{};
          calls.add({'path': request.url.path, 'body': body});

          if (request.url.path.endsWith('/auth/forgot-password')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'message': 'If an account exists for that email, a reset link was sent.',
                'data': {
                  'reset_url': 'http://localhost:3000/reset-password?token=tok_reset_123',
                },
              }),
              200,
            );
          }

          if (request.url.path.endsWith('/auth/reset-password')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'message': 'Password has been reset successfully.',
                'data': null,
              }),
              200,
            );
          }

          return http.Response(jsonEncode({'detail': 'Not found'}), 404);
        }),
      );

      final authProvider = AuthProvider(
        authService: AuthService(
          apiService: AuthApiService(client: mockClient),
        ),
      );

      await tester.pumpWidget(
        ChangeNotifierProvider<AuthProvider>.value(
          value: authProvider,
          child: const MaterialApp(
            home: Scaffold(body: ForgotPasswordScreen()),
          ),
        ),
      );

      await tester.enterText(
        find.byKey(const Key('forgot_password_email_field')),
        'shopper@example.com',
      );
      await tester.tap(find.byKey(const Key('send_reset_link_button')));
      await tester.pumpAndSettle();

      expect(calls.length, 1);
      expect(calls.first['path'], '/api/v1/auth/forgot-password');
      expect(calls.first['body']['email'], 'shopper@example.com');
      expect(find.byKey(const Key('reset_token_field')), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('new_password_field')),
        'StrongPass123!',
      );
      await tester.enterText(
        find.byKey(const Key('confirm_new_password_field')),
        'StrongPass123!',
      );
      await tester.tap(find.byKey(const Key('confirm_reset_password_button')));
      await tester.pumpAndSettle();

      expect(calls.length, 2);
      expect(calls[1]['path'], '/api/v1/auth/reset-password');
      expect(calls[1]['body']['token'], 'tok_reset_123');
      expect(calls[1]['body']['new_password'], 'StrongPass123!');
    });
  });
}
