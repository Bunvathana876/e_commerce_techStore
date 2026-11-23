import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/core/network/api_exceptions.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/auth/models/user_model.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/services/cart_api_service.dart';
import 'package:e_commerc_mobile_app/features/checkout/providers/checkout_provider.dart';
import 'package:e_commerc_mobile_app/features/checkout/services/stripe_payment_gateway.dart';
import 'package:e_commerc_mobile_app/features/notifications/providers/notification_provider.dart';
import 'package:e_commerc_mobile_app/features/notifications/services/notification_api_service.dart';
import 'package:e_commerc_mobile_app/features/orders/models/order_model.dart';
import 'package:e_commerc_mobile_app/features/orders/screens/order_tracking_screen.dart';
import 'package:e_commerc_mobile_app/features/orders/services/order_api_service.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';
import 'package:e_commerc_mobile_app/features/products/screens/product_detail_screen.dart';
import 'package:e_commerc_mobile_app/features/products/widgets/product_card.dart';
import 'package:e_commerc_mobile_app/features/reviews/providers/review_provider.dart';
import 'package:e_commerc_mobile_app/features/reviews/services/review_api_service.dart';

import '../support/checkout_api_fixture.dart';

class _FakeStripeGateway implements StripePaymentGateway {
  final bool shouldCancel;
  int calls = 0;
  String? lastPublishableKey;
  String? lastClientSecret;

  _FakeStripeGateway({this.shouldCancel = false});

  @override
  Future<void> presentCardPaymentSheet({
    required String publishableKey,
    required String clientSecret,
    String merchantDisplayName = 'Blue Panda',
    bool? isDarkTheme,
  }) async {
    calls++;
    lastPublishableKey = publishableKey;
    lastClientSecret = clientSecret;
    if (shouldCancel) {
      throw const StripePaymentSheetException(
        'Card payment was cancelled. Your order awaits payment confirmation.',
        cancelled: true,
      );
    }
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AuthProvider.clearLogoutListeners();
    AuthProvider.clearLoginListeners();
    ApiClient.instance.clearAuthToken();
  });

  group('Stripe PaymentSheet Mobile Checkout', () {
    final items = [
      {'product_id': 101, 'quantity': 1},
    ];

    test('card checkout runs intent -> PaymentSheet -> confirm and returns paid order', () async {
      final calls = <String>[];
      final fakeStripe = _FakeStripeGateway();

      final client = ApiClient(
        client: MockClient((request) async {
          calls.add('${request.method} ${request.url.path}');
          if (request.method == 'GET' && request.url.path.endsWith('/auth/me')) {
            return http.Response(jsonEncode({'success': true, 'data': {'id': 7}}), 200);
          }
          if (request.method == 'GET' && request.url.path.endsWith('/addresses')) {
            return http.Response(
              jsonEncode({'success': true, 'data': [checkoutAddress()]}),
              200,
            );
          }
          if (request.method == 'GET' && request.url.path.endsWith('/payments/config')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'supported_methods': ['Credit / Debit Card', 'Cash on Delivery'],
                  'card_gateway_configured': true,
                  'card_provider': 'stripe',
                  'stripe_publishable_key': 'pk_test_mobile_123',
                  'currency': 'USD',
                },
              }),
              200,
            );
          }
          if (request.method == 'POST' && request.url.path.endsWith('/orders')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'id': 880,
                  'user_id': 7,
                  'status': 'pending',
                  'subtotal': 120.0,
                  'discount_amount': 0.0,
                  'shipping_fee': 0.0,
                  'total': 120.0,
                  'payment_method': 'Credit / Debit Card',
                  'payment_status': 'pending',
                  'shipping_address': 'Phnom Penh',
                  'created_at': '2026-11-23T10:00:00Z',
                  'items': [],
                },
              }),
              201,
            );
          }
          if (request.method == 'POST' && request.url.path.endsWith('/payments/card/intent')) {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            expect(body['order_id'], 880);
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'payment_id': 12,
                  'transaction_ref': 'pi_mobile_880',
                  'order_id': 880,
                  'payment_intent_id': 'pi_mobile_880',
                  'client_secret': 'pi_mobile_880_secret_xyz',
                  'amount': 120.0,
                  'currency': 'usd',
                  'publishable_key': 'pk_test_mobile_123',
                },
              }),
              201,
            );
          }
          if (request.method == 'POST' && request.url.path.endsWith('/payments/card/confirm')) {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            expect(body['order_id'], 880);
            expect(body['payment_intent_id'], 'pi_mobile_880');
            return http.Response(
              jsonEncode({'success': true, 'data': {'id': 12, 'status': 'captured'}}),
              200,
            );
          }
          return http.Response('{"detail":"Unexpected path"}', 500);
        }),
      )..setAuthToken('jwt-user7');

      final checkout = CheckoutProvider(
        orders: OrderApiService(client: client),
        stripeGateway: fakeStripe,
      );
      addTearDown(checkout.dispose);

      await checkout.load();
      await checkout.refreshPaymentsConfig();
      expect(checkout.cardGatewayConfigured, isTrue);

      final result = await checkout.submit(
        items: items,
        paymentMethod: 'Credit / Debit Card',
      );
      expect(result, isNotNull);
      expect(result!.id, 880);
      expect(result.isPaid, isTrue);
      expect(fakeStripe.calls, 1);
      expect(fakeStripe.lastPublishableKey, 'pk_test_mobile_123');
      expect(fakeStripe.lastClientSecret, 'pi_mobile_880_secret_xyz');
      expect(calls.where((c) => c.contains('/payments/card/intent')), hasLength(1));
      expect(calls.where((c) => c.contains('/payments/card/confirm')), hasLength(1));
    });

    test('cancelling Stripe PaymentSheet preserves pending attempt for idempotent retry', () async {
      var confirmCalled = false;
      final fakeStripe = _FakeStripeGateway(shouldCancel: true);

      final client = ApiClient(
        client: MockClient((request) async {
          if (request.method == 'GET' && request.url.path.endsWith('/auth/me')) {
            return http.Response(jsonEncode({'success': true, 'data': {'id': 7}}), 200);
          }
          if (request.method == 'GET' && request.url.path.endsWith('/addresses')) {
            return http.Response(
              jsonEncode({'success': true, 'data': [checkoutAddress()]}),
              200,
            );
          }
          if (request.method == 'GET' && request.url.path.endsWith('/payments/config')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'card_gateway_configured': true,
                  'stripe_publishable_key': 'pk_test_mobile_123',
                },
              }),
              200,
            );
          }
          if (request.method == 'POST' && request.url.path.endsWith('/orders')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'id': 881,
                  'user_id': 7,
                  'status': 'pending',
                  'subtotal': 120.0,
                  'shipping_fee': 0.0,
                  'total': 120.0,
                  'payment_method': 'Credit / Debit Card',
                  'payment_status': 'pending',
                  'shipping_address': 'Phnom Penh',
                  'created_at': '2026-11-23T10:00:00Z',
                  'items': [],
                },
              }),
              201,
            );
          }
          if (request.method == 'POST' && request.url.path.endsWith('/payments/card/intent')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'payment_id': 13,
                  'transaction_ref': 'pi_cancel',
                  'order_id': 881,
                  'payment_intent_id': 'pi_cancel',
                  'client_secret': 'pi_cancel_secret',
                  'amount': 120.0,
                  'currency': 'usd',
                  'publishable_key': 'pk_test_mobile_123',
                },
              }),
              201,
            );
          }
          if (request.method == 'POST' && request.url.path.endsWith('/payments/card/confirm')) {
            confirmCalled = true;
            return http.Response('{}', 200);
          }
          return http.Response('{}', 500);
        }),
      )..setAuthToken('jwt-user7');

      final checkout = CheckoutProvider(
        orders: OrderApiService(client: client),
        stripeGateway: fakeStripe,
      );
      addTearDown(checkout.dispose);

      await checkout.load();
      await expectLater(
        checkout.submit(items: items, paymentMethod: 'Credit / Debit Card'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('cancelled'),
          ),
        ),
      );
      expect(confirmCalled, isFalse);
      expect(checkout.pending, isNotNull);
    });
  });

  group('Real OrderTrackingScreen', () {
    final sampleOrder = OrderModel(
      id: 404,
      userId: 7,
      status: 'shipped',
      subtotal: 95.0,
      shippingFee: 2.0,
      total: 97.0,
      paymentMethod: 'Cash on Delivery (COD)',
      paymentStatus: 'pending',
      shippingAddress: 'Street 2004, Phnom Penh',
      createdAt: DateTime(2026, 11, 22),
      items: const [
        OrderItemModel(
          id: 1,
          orderId: 404,
          productId: 10,
          productName: 'Canvas Backpack',
          price: 95.0,
          quantity: 1,
          subtotal: 95.0,
        ),
      ],
    );

    testWidgets('displays real carrier, tracking number, and events from backend', (
      WidgetTester tester,
    ) async {
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/orders/404/tracking')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'order_id': 404,
                  'order_status': 'shipped',
                  'payment_status': 'pending',
                  'shipping_address': 'Street 2004, Phnom Penh',
                  'has_shipment_record': true,
                  'shipment': {
                    'id': 3,
                    'order_id': 404,
                    'carrier': 'DHL Express',
                    'tracking_number': 'BP-TRK-9988',
                    'status': 'in_transit',
                    'estimated_delivery_at': '2026-11-26T10:00:00Z',
                  },
                  'events': [
                    {
                      'id': 9,
                      'status': 'in_transit',
                      'title': 'Dispatched from Phnom Penh Hub',
                      'description': 'Parcel departed sorting facility',
                      'location': 'Phnom Penh',
                      'occurred_at': '2026-11-23T08:00:00Z',
                    },
                  ],
                },
              }),
              200,
            );
          }
          return http.Response('{"detail":"Not found"}', 404);
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: OrderTrackingScreen(
            order: sampleOrder,
            orderApiService: OrderApiService(client: client),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('DHL Express'), findsOneWidget);
      expect(find.text('BP-TRK-9988'), findsOneWidget);
      expect(find.text('Dispatched from Phnom Penh Hub'), findsOneWidget);
      expect(find.text('Sokha Rith'), findsNothing);
      expect(find.text('Live GPS Connected'), findsNothing);
    });

    testWidgets('shows Retry banner cleanly on offline tracking failure and recovers on Retry', (
      WidgetTester tester,
    ) async {
      var shouldFail = true;
      final client = ApiClient(
        client: MockClient((request) async {
          if (shouldFail) {
            return http.Response('{"detail":"Tracking service offline"}', 503);
          }
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'order_id': 404,
                'order_status': 'shipped',
                'payment_status': 'pending',
                'shipping_address': 'Street 2004, Phnom Penh',
                'has_shipment_record': true,
                'shipment': {
                  'id': 3,
                  'order_id': 404,
                  'carrier': 'FedEx',
                  'tracking_number': 'FX-1234',
                  'status': 'shipped',
                },
                'events': [],
              },
            }),
            200,
          );
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: OrderTrackingScreen(
            order: sampleOrder,
            orderApiService: OrderApiService(client: client),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Retry'), findsOneWidget);
      expect(find.text('FedEx'), findsNothing);

      shouldFail = false;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();

      expect(find.text('Retry'), findsNothing);
      expect(find.text('FedEx'), findsOneWidget);
      expect(find.text('FX-1234'), findsOneWidget);
    });
  });

  group('Cart Login Sync, Product Stock, Notifications & Reviews Fixes', () {
    test('CartProvider loads remote cart when AuthProvider saves a user session', () async {
      var cartFetchCount = 0;
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.method == 'GET' && request.url.path.endsWith('/cart')) {
            cartFetchCount++;
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'items': [
                    {
                      'id': 1,
                      'product_id': 55,
                      'quantity': 2,
                      'product': {
                        'id': 55,
                        'name': 'Remote Synced Headphones',
                        'description': 'Synced from backend cart',
                        'price': 80.0,
                        'rating': 4.8,
                        'review_count': 12,
                        'category_id': 1,
                        'stock': 6,
                        'is_active': true,
                        'image_url': '',
                      },
                    },
                  ],
                },
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      )..setAuthToken('jwt-remote');

      final cartProvider = CartProvider(
        cartApiService: CartApiService(client: client),
      );
      addTearDown(cartProvider.dispose);
      expect(cartFetchCount, 0);

      final authProvider = AuthProvider();
      await authProvider.saveUserSession(
        token: 'jwt-remote',
        user: const UserModel(
          id: 7,
          email: 'buyer@example.com',
          fullName: 'Buyer',
          role: 'customer',
        ),
      );
      // Allow unawaited async login listener to complete
      await Future<void>.delayed(const Duration(milliseconds: 20));

      expect(cartFetchCount, 1);
      expect(cartProvider.items, hasLength(1));
      expect(cartProvider.items.first.product.name, 'Remote Synced Headphones');
      expect(cartProvider.items.first.quantity, 2);
    });

    testWidgets('ProductCard and ProductDetailScreen enforce stock & isActive state', (
      WidgetTester tester,
    ) async {
      final outOfStock = ProductModel.fromJson({
        'id': 90,
        'name': 'Limited Jacket',
        'description': 'Sold out',
        'price': 90.0,
        'rating': 4.5,
        'review_count': 5,
        'category_id': 2,
        'stock': 0,
        'is_active': true,
        'image_url': '',
      });
      final lowStock = ProductModel(
        id: 91,
        name: 'Studio Mic',
        description: 'Low stock',
        price: 110.0,
        rating: 4.9,
        reviewCount: 9,
        categoryId: 1,
        stock: 2,
        isActive: true,
        imageUrl: '',
      );

      expect(outOfStock.isOutOfStock, isTrue);
      expect(lowStock.isLowStock, isTrue);

      final cartProvider = CartProvider(useRemoteBackend: false);
      cartProvider.addItem(outOfStock);
      expect(cartProvider.items, isEmpty);
      cartProvider.addItem(lowStock, quantity: 5);
      expect(cartProvider.items.single.quantity, 2);

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: Row(
              children: [
                SizedBox(
                  width: 170,
                  height: 260,
                  child: ProductCard(
                    product: outOfStock,
                    onTap: () {},
                    onToggleFavorite: () {},
                  ),
                ),
                SizedBox(
                  width: 170,
                  height: 260,
                  child: ProductCard(
                    product: lowStock,
                    onTap: () {},
                    onToggleFavorite: () {},
                  ),
                ),
              ],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('OUT OF STOCK'), findsOneWidget);
      expect(find.text('2 left'), findsOneWidget);

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ProductProvider>(create: (_) => ProductProvider()),
            ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
            ChangeNotifierProvider<ReviewProvider>(create: (_) => ReviewProvider()),
            ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: ProductDetailScreen(product: outOfStock),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Out of Stock'), findsOneWidget);
      final countBeforeTap = cartProvider.items.length;
      await tester.tap(find.byKey(const Key('add_to_cart_button')));
      await tester.pump();
      expect(cartProvider.items.length, countBeforeTap);
    });

    test('NotificationProvider resets clear flag when new server notifications arrive', () async {
      var returnNewNotifications = false;
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/notifications')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': returnNewNotifications
                    ? [
                        {
                          'id': 505,
                          'type': 'order',
                          'title': 'Order Shipped',
                          'message': 'Tracking ready',
                          'read': false,
                          'created_at': '2026-11-23T09:00:00Z',
                        },
                      ]
                    : [],
              }),
              200,
            );
          }
          if (request.url.path.endsWith('/notifications/unread-count')) {
            return http.Response(
              jsonEncode({'success': true, 'data': {'unread_count': returnNewNotifications ? 1 : 0}}),
              200,
            );
          }
          return http.Response(jsonEncode({'success': true}), 200);
        }),
      );

      final provider = NotificationProvider(
        apiService: NotificationApiService(client: client),
      );
      addTearDown(provider.dispose);

      await provider.clearAll();
      expect(provider.notifications, isEmpty);

      await provider.loadNotifications(silent: true);
      expect(provider.notifications, isEmpty);

      returnNewNotifications = true;
      await provider.loadNotifications(silent: true);
      expect(provider.notifications, hasLength(1));
      expect(provider.notifications.single.id, 505);
      expect(provider.unreadCount, 1);
    });

    test('ReviewProvider.submitReview returns false on API failure instead of faking success', () async {
      final failingClient = ApiClient(
        client: MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'Only customers who have purchased this product can submit a review.'}),
            403,
          );
        }),
      );

      final reviewProvider = ReviewProvider(
        apiService: ReviewApiService(client: failingClient),
      );
      final ok = await reviewProvider.submitReview(
        productId: 13,
        rating: 5,
        comment: 'Trying without buying',
      );
      expect(ok, isFalse);
      expect(reviewProvider.errorMessage, isNotNull);
      expect(reviewProvider.getReviews(13), isEmpty);
    });

    test('CartProvider applies public store shipping rules and CheckoutProvider enforces disabled payment methods', () async {
      final settingsClient = ApiClient(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/settings/public')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'store_name': 'Blue Panda',
                  'store_email': 'support@bluepanda.com',
                  'currency': 'USD',
                  'free_shipping_min': 200.0,
                  'standard_shipping_fee': 6.0,
                  'express_shipping_fee': 12.0,
                  'estimated_delivery_days': '1-3',
                  'enable_card_payment': false,
                  'enable_cod_payment': false,
                },
              }),
              200,
            );
          }
          if (request.url.path.endsWith('/auth/me')) {
            return http.Response(jsonEncode({'success': true, 'data': {'id': 7}}), 200);
          }
          if (request.url.path.endsWith('/addresses')) {
            return http.Response(
              jsonEncode({'success': true, 'data': [checkoutAddress()]}),
              200,
            );
          }
          if (request.url.path.endsWith('/payments/config')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'supported_methods': [],
                  'card_gateway_configured': false,
                  'enable_card_payment': false,
                  'enable_cod_payment': false,
                },
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      )..setAuthToken('jwt-user7');

      final cartProvider = CartProvider(
        cartApiService: CartApiService(client: settingsClient),
      );
      addTearDown(cartProvider.dispose);
      cartProvider.addItem(
        const ProductModel(
          id: 99,
          name: 'Mechanical Keyboard',
          description: 'Tactile',
          price: 120.0,
          rating: 4.8,
          reviewCount: 5,
          categoryId: 1,
          stock: 10,
          imageUrl: '',
        ),
      );
      await cartProvider.loadPublicShippingSettings();
      expect(cartProvider.shippingFee, 6.0);
      expect(cartProvider.grandTotal, 126.0);

      final checkout = CheckoutProvider(
        orders: OrderApiService(client: settingsClient),
      );
      addTearDown(checkout.dispose);
      await checkout.load();
      await checkout.refreshPaymentsConfig();

      await expectLater(
        checkout.submit(
          items: [
            {'product_id': 99, 'quantity': 1},
          ],
          paymentMethod: 'Cash on Delivery (COD)',
        ),
        throwsA(
          isA<ApiException>().having(
            (e) => e.message,
            'message',
            contains('disabled in store settings'),
          ),
        ),
      );
    });
  });
}
