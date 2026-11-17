import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/core/network/api_exceptions.dart';
import 'package:e_commerc_mobile_app/features/auth/models/user_model.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_api_service.dart';
import 'package:e_commerc_mobile_app/features/auth/services/auth_service.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/services/cart_api_service.dart';
import 'package:e_commerc_mobile_app/features/notifications/providers/notification_provider.dart';
import 'package:e_commerc_mobile_app/features/orders/models/order_model.dart';
import 'package:e_commerc_mobile_app/features/orders/providers/order_provider.dart';
import 'package:e_commerc_mobile_app/features/orders/services/order_api_service.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

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

  const sampleUserA = UserModel(
    id: 1,
    email: 'usera@example.com',
    fullName: 'User Alpha',
    role: 'customer',
  );

  const sampleUserB = UserModel(
    id: 2,
    email: 'userb@example.com',
    fullName: 'User Beta',
    role: 'customer',
  );

  const testProduct1 = ProductModel(
    id: 101,
    name: 'Wireless Headphones',
    description: 'High fidelity audio headphones',
    price: 99.99,
    rating: 4.8,
    reviewCount: 42,
    categoryId: 1,
    imageUrl: 'https://example.com/headphones.jpg',
  );

  group('Flutter Session Isolation & Logout Cache Security (S14)', () {
    test('1. Logout clears tokens, user data, and ApiClient authorization', () async {
      SharedPreferences.setMockInitialValues({
        'auth_token': 'jwt_alpha_token',
        'auth_user': jsonEncode(sampleUserA.toJson()),
      });
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);

      expect(authProvider.isAuthenticated, isTrue);
      expect(ApiClient.instance.isAuthenticated, isTrue);

      await authProvider.logout();

      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.currentUser, isNull);
      expect(authProvider.token, isNull);
      expect(ApiClient.instance.isAuthenticated, isFalse);
      expect(ApiClient.instance.authToken, isNull);

      final updatedPrefs = await SharedPreferences.getInstance();
      expect(updatedPrefs.getString('auth_token'), isNull);
      expect(updatedPrefs.getString('auth_user'), isNull);
    });

    test('2. Logout clears cached orders, notification state, but strictly preserves app_theme_mode', () async {
      SharedPreferences.setMockInitialValues({
        'auth_token': 'jwt_alpha_token',
        'auth_user': jsonEncode(sampleUserA.toJson()),
        'user_orders_cache': jsonEncode([
          {
            'id': 1001,
            'items': [],
            'subtotal': 50.0,
            'discount': 0.0,
            'shipping': 0.0,
            'total': 50.0,
            'status': 'delivered',
            'created_at': DateTime.now().toIso8601String(),
          }
        ]),
        'notifications_has_cleared': true,
        'notifications_deleted_ids': ['1', '2'],
        'app_theme_mode': 'dark',
      });
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);

      await authProvider.logout();

      final updatedPrefs = await SharedPreferences.getInstance();
      expect(updatedPrefs.getString('auth_token'), isNull);
      expect(updatedPrefs.getString('auth_user'), isNull);
      expect(updatedPrefs.getString('user_orders_cache'), isNull);
      expect(updatedPrefs.getBool('notifications_has_cleared'), isNull);
      expect(updatedPrefs.getStringList('notifications_deleted_ids'), isNull);

      // Non-sensitive theme preference MUST remain intact
      expect(updatedPrefs.getString('app_theme_mode'), 'dark');
    });

    test('3. Logout clears in-memory cart, applied coupons, and orders across providers', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);
      final cartProvider = CartProvider(useRemoteBackend: false);
      final orderProvider = OrderProvider(initialPrefs: prefs);

      // User populates cart and orders
      cartProvider.addItem(testProduct1, quantity: 2);
      expect(cartProvider.totalItemsCount, 2);

      orderProvider.recordOrder(OrderModel(
        id: 501,
        userId: 1,
        items: const [],
        subtotal: 100.0,
        discountAmount: 0.0,
        shippingFee: 0.0,
        total: 100.0,
        paymentMethod: 'cod',
        paymentStatus: 'pending',
        shippingAddress: '123 Main St',
        status: 'pending',
        createdAt: DateTime.now(),
      ));
      expect(orderProvider.orders.length, 1);

      // Logout
      await authProvider.logout();

      // Both providers must be completely cleared
      expect(cartProvider.items, isEmpty);
      expect(cartProvider.totalItemsCount, 0);
      expect(orderProvider.orders, isEmpty);
    });

    test('4. Logout clears favorites from ProductProvider', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);
      final productProvider = ProductProvider(initialProducts: [
        testProduct1.copyWith(isFavorite: true),
      ]);

      expect(productProvider.favoriteProducts.length, 1);

      await authProvider.logout();

      expect(productProvider.favoriteProducts, isEmpty);
    });

    test('5. Logout clears notifications in NotificationProvider', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);
      final notificationProvider = NotificationProvider(initialPrefs: prefs);

      await authProvider.logout();

      expect(notificationProvider.notifications, isEmpty);
      expect(notificationProvider.unreadCount, 0);
    });

    test('6. User switching (User A -> logout -> User B) guarantees complete data isolation', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final mockHttp = MockClient((request) async {
        if (request.url.path.contains('/auth/login')) {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          if (body['email'] == 'usera@example.com') {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'access_token': 'token_alpha',
                  'user': sampleUserA.toJson(),
                },
              }),
              200,
            );
          } else {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'access_token': 'token_beta',
                  'user': sampleUserB.toJson(),
                },
              }),
              200,
            );
          }
        }
        return http.Response(jsonEncode({'success': true, 'data': []}), 200);
      });

      final apiClient = ApiClient(client: mockHttp);
      final authProvider = AuthProvider(
        authService: AuthService(apiService: AuthApiService(client: apiClient)),
        initialPrefs: prefs,
      );
      final cartProvider = CartProvider(
        cartApiService: CartApiService(client: apiClient),
        useRemoteBackend: false,
      );
      final orderProvider = OrderProvider(
        apiService: OrderApiService(client: apiClient),
        initialPrefs: prefs,
      );

      // Login User A
      await authProvider.login('usera@example.com', 'pass123');
      expect(authProvider.currentUser?.email, 'usera@example.com');

      cartProvider.addItem(testProduct1, quantity: 3);
      orderProvider.recordOrder(OrderModel(
        id: 701,
        userId: 1,
        items: const [],
        subtotal: 99.99,
        discountAmount: 0.0,
        shippingFee: 0.0,
        total: 99.99,
        paymentMethod: 'card',
        paymentStatus: 'paid',
        shippingAddress: '456 Elm St',
        status: 'pending',
        createdAt: DateTime.now(),
      ));

      expect(cartProvider.totalItemsCount, 3);
      expect(orderProvider.orders.length, 1);

      // User A logs out
      await authProvider.logout();

      expect(cartProvider.items, isEmpty);
      expect(orderProvider.orders, isEmpty);

      // Login User B
      await authProvider.login('userb@example.com', 'pass123');
      expect(authProvider.currentUser?.email, 'userb@example.com');

      // User B must not see any of User A's cart items or orders
      expect(cartProvider.items, isEmpty);
      expect(orderProvider.orders, isEmpty);
    });

    test('7. Delayed in-flight fetchOrders response from User A is dropped after logout', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final completer = Completer<http.Response>();
      final mockHttp = MockClient((request) async {
        if (request.url.path.contains('/orders')) {
          return await completer.future;
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final client = ApiClient(client: mockHttp);
      client.setAuthToken('token_user_a');

      final authProvider = AuthProvider(initialPrefs: prefs);
      final orderProvider = OrderProvider(
        apiService: OrderApiService(client: client),
        initialPrefs: prefs,
      );

      // Trigger fetchOrders while authenticated as User A
      final fetchFuture = orderProvider.fetchOrders();

      // User logs out before response finishes
      await authProvider.logout();

      // Late response arrives with User A orders
      completer.complete(http.Response(
        jsonEncode({
          'success': true,
          'data': [
            {
              'id': 999,
              'items': [],
              'subtotal': 250.0,
              'discount': 0.0,
              'shipping': 0.0,
              'total': 250.0,
              'status': 'processing',
              'created_at': DateTime.now().toIso8601String(),
            }
          ],
        }),
        200,
      ));

      await fetchFuture;

      // In-flight response was safely dropped because session epoch changed
      expect(orderProvider.orders, isEmpty);
      final storedPrefs = await SharedPreferences.getInstance();
      expect(storedPrefs.getString('user_orders_cache'), isNull);
    });

    test('8. Delayed in-flight loadRemoteCart response from User A is dropped after logout', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final completer = Completer<http.Response>();
      final mockHttp = MockClient((request) async {
        if (request.url.path.contains('/cart')) {
          return await completer.future;
        }
        return http.Response(jsonEncode({'success': true, 'data': {}}), 200);
      });

      final client = ApiClient(client: mockHttp);
      client.setAuthToken('token_user_a');

      final authProvider = AuthProvider(initialPrefs: prefs);
      final cartProvider = CartProvider(
        cartApiService: CartApiService(client: client),
      );

      // Start fetching remote cart
      final cartFuture = cartProvider.loadRemoteCart();

      // User logs out while request is running
      await authProvider.logout();

      // Response finally arrives
      completer.complete(http.Response(
        jsonEncode({
          'success': true,
          'data': [
            {
              'id': 1,
              'product': testProduct1.toJson(),
              'quantity': 5,
              'variant': 'Standard',
            }
          ],
        }),
        200,
      ));

      await cartFuture;

      // Response dropped, cart stays empty
      expect(cartProvider.items, isEmpty);
    });

    test('9. 401 Unauthorized API error triggers automatic logout and session cleanup', () async {
      SharedPreferences.setMockInitialValues({
        'auth_token': 'expired_token_xyz',
        'auth_user': jsonEncode(sampleUserA.toJson()),
      });
      final prefs = await SharedPreferences.getInstance();

      final mockHttp = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Token expired or invalid'}),
          401,
        );
      });

      final client = ApiClient(client: mockHttp);
      final authProvider = AuthProvider(
        authService: AuthService(apiService: AuthApiService(client: client)),
        initialPrefs: prefs,
      );

      expect(authProvider.isAuthenticated, isTrue);

      // Execute request that fails with 401
      expect(
        () => client.get<dynamic>('/api/v1/orders'),
        throwsA(isA<UnauthorizedException>()),
      );

      // Allow microtask / unawaited logout to complete
      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.currentUser, isNull);
      expect(authProvider.token, isNull);
      expect(ApiClient.instance.isAuthenticated, isFalse);

      final updatedPrefs = await SharedPreferences.getInstance();
      expect(updatedPrefs.getString('auth_token'), isNull);
      expect(updatedPrefs.getString('auth_user'), isNull);
    });

    test('10. Partial or corrupted session in SharedPreferences is discarded on startup', () async {
      // Token exists but auth_user is missing or invalid JSON
      SharedPreferences.setMockInitialValues({
        'auth_token': 'orphan_token_123',
        'auth_user': '{invalid_json',
      });
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);

      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.token, isNull);
      expect(authProvider.currentUser, isNull);
      expect(ApiClient.instance.isAuthenticated, isFalse);
    });

    test('11. Direct login wipes un-cleared prior session artifacts before new user binding', () async {
      SharedPreferences.setMockInitialValues({
        'user_orders_cache': jsonEncode([
          {
            'id': 888,
            'items': [],
            'subtotal': 120.0,
            'discount': 0.0,
            'shipping': 0.0,
            'total': 120.0,
            'status': 'delivered',
            'created_at': DateTime.now().toIso8601String(),
          }
        ]),
      });
      final prefs = await SharedPreferences.getInstance();

      final mockHttp = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'access_token': 'new_user_token',
              'user': sampleUserB.toJson(),
            },
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockHttp);
      final authProvider = AuthProvider(
        authService: AuthService(apiService: AuthApiService(client: apiClient)),
        initialPrefs: prefs,
      );
      final orderProvider = OrderProvider(
        apiService: OrderApiService(client: apiClient),
        initialPrefs: prefs,
      );

      expect(orderProvider.orders.length, 1);

      // Login new user without prior explicit logout
      await authProvider.login('userb@example.com', 'password123');

      // Previous user's cached orders must be cleared
      expect(orderProvider.orders, isEmpty);
      final updatedPrefs = await SharedPreferences.getInstance();
      expect(updatedPrefs.getString('user_orders_cache'), isNull);
    });
  });
}
