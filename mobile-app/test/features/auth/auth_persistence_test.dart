import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/app/app.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/features/auth/models/user_model.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_api_service.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_service.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/categories/providers/category_provider.dart';
import 'package:e_commerc_mobile_app/features/navigation/main_navigation_screen.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';
import 'package:e_commerc_mobile_app/features/profile/settings/providers/theme_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  tearDown(() {
    ApiClient.instance.clearAuthToken();
  });

  group('Auth Persistence Tests', () {
    test('login persists backend token and user data to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final mockHttp = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'access_token': 'real_backend_jwt_token',
              'user': {
                'id': 7,
                'email': 'customer@ecommerce.com',
                'full_name': 'Customer Demo',
                'role': 'customer',
              },
            },
          }),
          200,
        );
      });
      final authProvider = AuthProvider(
        authService: AuthService(
          apiService: AuthApiService(client: ApiClient(client: mockHttp)),
        ),
      );

      final success = await authProvider.login(
        'customer@ecommerce.com',
        'password123',
      );

      expect(success, isTrue);
      expect(authProvider.isAuthenticated, isTrue);
      expect(authProvider.token, 'real_backend_jwt_token');
      expect(authProvider.currentUser?.fullName, 'Customer Demo');

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('auth_token'), 'real_backend_jwt_token');
      expect(prefs.getString('auth_user'), contains('customer@ecommerce.com'));
    });

    test(
      'backend login failure never creates a fake session even for demo credentials',
      () async {
        SharedPreferences.setMockInitialValues({});
        final failingHttp = MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'Invalid email or password'}),
            401,
          );
        });
        final authProvider = AuthProvider(
          authService: AuthService(
            apiService: AuthApiService(client: ApiClient(client: failingHttp)),
          ),
        );

        final success = await authProvider.login(
          'student@example.com',
          'password123',
        );

        expect(success, isFalse);
        expect(authProvider.isAuthenticated, isFalse);
        expect(authProvider.token, isNull);
        expect(authProvider.currentUser, isNull);
        expect(authProvider.errorMessage, contains('Invalid email or password'));
        expect(ApiClient.instance.isAuthenticated, isFalse);

        final prefs = await SharedPreferences.getInstance();
        expect(prefs.getString('auth_token'), isNull);
        expect(prefs.getString('auth_user'), isNull);
      },
    );

    test(
      'malformed backend login response without token does not create authenticated session',
      () async {
        SharedPreferences.setMockInitialValues({});
        final malformedHttp = MockClient((request) async {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'user': {
                  'id': 1,
                  'email': 'student@example.com',
                  'full_name': 'Bun Vathana',
                  'role': 'customer',
                },
              },
            }),
            200,
          );
        });
        final authProvider = AuthProvider(
          authService: AuthService(
            apiService: AuthApiService(client: ApiClient(client: malformedHttp)),
          ),
        );

        final success = await authProvider.login(
          'student@example.com',
          'password123',
        );

        expect(success, isFalse);
        expect(authProvider.isAuthenticated, isFalse);
        expect(authProvider.token, isNull);
        expect(authProvider.currentUser, isNull);
      },
    );

    test(
      'explicit offline demo mode (useRemoteBackend: false) remains isolated from production',
      () async {
        SharedPreferences.setMockInitialValues({});
        final demoProvider = AuthProvider(
          authService: AuthService(useRemoteBackend: false),
        );

        final success = await demoProvider.login(
          'student@example.com',
          'password123',
        );

        expect(success, isTrue);
        expect(demoProvider.isAuthenticated, isTrue);
      },
    );

    test(
      'backend signUp failure never creates fake session even for test/mock/example.com emails',
      () async {
        SharedPreferences.setMockInitialValues({});
        final failingHttp = MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'An account with this email already exists.'}),
            400,
          );
        });
        final authProvider = AuthProvider(
          authService: AuthService(
            apiService: AuthApiService(client: ApiClient(client: failingHttp)),
          ),
        );

        for (final email in [
          'alice@example.com',
          'test.user@domain.com',
          'mock_account@domain.com',
        ]) {
          final success = await authProvider.signUp(
            fullName: 'Test User',
            email: email,
            password: 'password123',
          );

          expect(success, isFalse);
          expect(authProvider.isAuthenticated, isFalse);
          expect(authProvider.token, isNull);
          expect(authProvider.currentUser, isNull);
          expect(ApiClient.instance.isAuthenticated, isFalse);
        }

        final prefs = await SharedPreferences.getInstance();
        expect(prefs.getString('auth_token'), isNull);
        expect(prefs.getString('auth_user'), isNull);
      },
    );

    test(
      'AuthProvider restores user session when initialized with saved prefs',
      () async {
        const mockUser = UserModel(
          id: 1,
          email: 'saved_user@example.com',
          fullName: 'Saved User',
          role: 'customer',
        );

        SharedPreferences.setMockInitialValues({
          'auth_token': 'saved_jwt_token',
          'auth_user': jsonEncode(mockUser.toJson()),
        });

        final prefs = await SharedPreferences.getInstance();
        final authProvider = AuthProvider(initialPrefs: prefs);

        expect(authProvider.isAuthenticated, isTrue);
        expect(authProvider.token, 'saved_jwt_token');
        expect(authProvider.currentUser?.email, 'saved_user@example.com');
        expect(authProvider.currentUser?.fullName, 'Saved User');
      },
    );

    test(
      'logout clears persistent token and user data from SharedPreferences',
      () async {
        SharedPreferences.setMockInitialValues({
          'auth_token': 'token_to_remove',
          'auth_user': jsonEncode({
            'id': 2,
            'email': 'remove_me@example.com',
            'full_name': 'Remove Me',
            'role': 'customer',
          }),
        });

        final prefs = await SharedPreferences.getInstance();
        final authProvider = AuthProvider(initialPrefs: prefs);
        expect(authProvider.isAuthenticated, isTrue);

        await authProvider.logout();

        expect(authProvider.isAuthenticated, isFalse);
        expect(authProvider.currentUser, isNull);
        expect(authProvider.token, isNull);

        final updatedPrefs = await SharedPreferences.getInstance();
        expect(updatedPrefs.getString('auth_token'), isNull);
        expect(updatedPrefs.getString('auth_user'), isNull);
      },
    );

    testWidgets(
      'App opens directly to MainNavigationScreen when user is already logged in',
      (WidgetTester tester) async {
        const savedUser = UserModel(
          id: 1,
          email: 'student@example.com',
          fullName: 'Bun Vathana',
          role: 'customer',
        );

        SharedPreferences.setMockInitialValues({
          'auth_token': 'valid_token',
          'auth_user': jsonEncode(savedUser.toJson()),
        });

        final prefs = await SharedPreferences.getInstance();
        final authProvider = AuthProvider(initialPrefs: prefs);

        await tester.pumpWidget(
          MultiProvider(
            providers: [
              ChangeNotifierProvider.value(value: authProvider),
              ChangeNotifierProvider(create: (_) => ProductProvider()),
              ChangeNotifierProvider(create: (_) => CartProvider()),
              ChangeNotifierProvider(create: (_) => CategoryProvider()),
              ChangeNotifierProvider(create: (_) => ThemeProvider()),
            ],
            child: const MyApp(),
          ),
        );

        // Verify MainNavigationScreen renders instead of Welcome Screen
        expect(find.byType(MainNavigationScreen), findsOneWidget);
        expect(find.text('Categories'), findsWidgets);
      },
    );
  });
}
