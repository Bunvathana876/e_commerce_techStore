import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import '../../support/checkout_api_fixture.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/services/cart_api_service.dart';
import 'package:e_commerc_mobile_app/features/checkout/screens/checkout_screen.dart';
import 'package:e_commerc_mobile_app/features/checkout/screens/order_success_screen.dart';
import 'package:e_commerc_mobile_app/features/orders/models/order_model.dart';
import 'package:e_commerc_mobile_app/features/orders/providers/order_provider.dart';
import 'package:e_commerc_mobile_app/features/orders/services/order_api_service.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const sampleProduct = ProductModel(
    id: 101,
    name: 'UltraBook Pro 15" M2 Laptop',
    description: 'High performance laptop.',
    price: 120.00,
    rating: 4.9,
    reviewCount: 312,
    categoryId: 1,
    imageUrl: '',
  );

  setUp(() => SharedPreferences.setMockInitialValues({}));

  tearDown(() {
    ApiClient.instance.clearAuthToken();
  });

  group('Checkout, Order, Payment & Coupon Security Tests', () {
    testWidgets(
      '1-3. Failed backend checkout preserves cart, records no order, and stays off OrderSuccessScreen',
      (WidgetTester tester) async {
        SharedPreferences.setMockInitialValues({});
        final prefs = await SharedPreferences.getInstance();
        final orderProvider = OrderProvider(initialPrefs: prefs);
        final cartProvider = CartProvider();
        cartProvider.addItem(sampleProduct, quantity: 2);

        final failingClient = ApiClient(
          client: checkoutClient((request) async {
            return http.Response(
              jsonEncode({'detail': 'Insufficient stock for UltraBook Pro'}),
              400,
            );
          }),
        )..setAuthToken('valid_backend_jwt');

        await tester.pumpWidget(
          MultiProvider(
            providers: [
              ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
              ChangeNotifierProvider<OrderProvider>.value(value: orderProvider),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: CheckoutScreen(
                orderApiService: OrderApiService(client: failingClient),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        await tester.tap(find.byKey(const Key('place_order_button')));
        await tester.pumpAndSettle();

        // 1. No confirmed order created
        expect(orderProvider.orders, isEmpty);
        // 2. Did not navigate to OrderSuccessScreen; shows error SnackBar
        expect(find.byType(OrderSuccessScreen), findsNothing);
        expect(find.byType(CheckoutScreen), findsOneWidget);
        expect(
          find.textContaining('Insufficient stock for UltraBook Pro'),
          findsOneWidget,
        );
        // 3. Cart items remain available
        expect(cartProvider.isEmpty, isFalse);
        expect(cartProvider.totalItemsCount, 2);
      },
    );

    testWidgets(
      'Unauthenticated checkout attempt preserves cart, creates no fake order, and shows sign-in message',
      (WidgetTester tester) async {
        SharedPreferences.setMockInitialValues({});
        final prefs = await SharedPreferences.getInstance();
        final orderProvider = OrderProvider(initialPrefs: prefs);
        final cartProvider = CartProvider();
        cartProvider.addItem(sampleProduct, quantity: 1);

        final unauthenticatedClient = ApiClient(
          client: checkoutClient((request) async {
            fail('Unauthenticated checkout should not send order request');
          }),
        );

        await tester.pumpWidget(
          MultiProvider(
            providers: [
              ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
              ChangeNotifierProvider<OrderProvider>.value(value: orderProvider),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: CheckoutScreen(
                orderApiService: OrderApiService(client: unauthenticatedClient),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('place_order_button')));
        await tester.pumpAndSettle();

        expect(orderProvider.orders, isEmpty);
        expect(find.byType(OrderSuccessScreen), findsNothing);
        expect(find.text('Please sign in to place an order.'), findsWidgets);
        expect(cartProvider.totalItemsCount, 1);
      },
    );

    testWidgets(
      'Prevents duplicate order submissions while request is in flight',
      (WidgetTester tester) async {
        final completer = Completer<http.Response>();
        var requestCount = 0;

        final slowClient = ApiClient(
          client: checkoutClient((request) {
            requestCount++;
            return completer.future;
          }),
        )..setAuthToken('valid_backend_jwt');

        final cartProvider = CartProvider();
        cartProvider.addItem(sampleProduct, quantity: 1);

        await tester.pumpWidget(
          ChangeNotifierProvider<CartProvider>.value(
            value: cartProvider,
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: CheckoutScreen(
                orderApiService: OrderApiService(client: slowClient),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        // Rapid double-tap while first submission is still in flight
        await tester.tap(find.byKey(const Key('place_order_button')));
        await tester.pump();
        await tester.tap(find.byKey(const Key('place_order_button')));
        await tester.pump();

        expect(requestCount, 1);

        completer.complete(
          http.Response(jsonEncode({'detail': 'Temporary server outage'}), 500),
        );
        await tester.pumpAndSettle();

        expect(cartProvider.totalItemsCount, 1);
        expect(find.byType(OrderSuccessScreen), findsNothing);
      },
    );

    testWidgets('4. Demo payments cannot submit real orders', (
      WidgetTester tester,
    ) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final orderProvider = OrderProvider(initialPrefs: prefs);
      final cartProvider = CartProvider();
      cartProvider.addItem(sampleProduct, quantity: 1);

      // Attempt online Credit / Debit Card checkout while Stripe card gateway is unconfigured:
      // unconfigured card checkout must be blocked client-side before order creation.
      final cardBlockedClient = ApiClient(
        client: checkoutClient((request) async {
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'id': 777,
                'user_id': 7,
                'status': 'pending',
                'subtotal': 120.0,
                'discount_amount': 0.0,
                'shipping_fee': 0.0,
                'total': 120.0,
                'payment_method': 'Credit / Debit Card',
                'payment_status': 'pending',
                'shipping_address': 'Phnom Penh',
                'created_at': '2026-10-31T10:00:00Z',
                'items': [],
              },
            }),
            201,
          );
        }),
      )..setAuthToken('valid_backend_jwt');

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
            ChangeNotifierProvider<OrderProvider>.value(value: orderProvider),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: CheckoutScreen(
              orderApiService: OrderApiService(client: cardBlockedClient),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Select Credit / Debit Card (index 1) and submit while gateway is unconfigured
      await tester.scrollUntilVisible(
        find.byKey(const Key('payment_method_1')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('payment_method_1')));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('place_order_button')));
      await tester.pumpAndSettle();

      expect(orderProvider.orders, isEmpty);
      expect(find.byType(OrderSuccessScreen), findsNothing);
      expect(
        find.textContaining('Online card payments are not available right now'),
        findsOneWidget,
      );
      expect(cartProvider.isEmpty, isFalse);
    });

    test(
      'OrderProvider ignores unconfirmed local IDs (<= 0) and replaces stale local cache on server sync',
      () async {
        SharedPreferences.setMockInitialValues({
          'user_orders_cache': jsonEncode([
            {
              'id': 0,
              'user_id': 7,
              'status': 'pending',
              'subtotal': 10.0,
              'shipping_fee': 2.0,
              'total': 12.0,
              'payment_method': 'Cash on Delivery (COD)',
              'payment_status': 'unpaid',
              'shipping_address': 'Draft order',
              'created_at': '2026-10-31T09:00:00Z',
              'items': [],
            },
          ]),
        });
        final prefs = await SharedPreferences.getInstance();
        final syncClient = ApiClient(
          client: checkoutClient((request) async {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': [
                  {
                    'id': 900,
                    'user_id': 7,
                    'status': 'pending',
                    'subtotal': 45.0,
                    'shipping_fee': 2.0,
                    'total': 47.0,
                    'payment_method': 'Cash on Delivery (COD)',
                    'payment_status': 'pending',
                    'shipping_address': 'Phnom Penh',
                    'created_at': '2026-10-31T10:00:00Z',
                    'items': [],
                  },
                ],
              }),
              200,
            );
          }),
        )..setAuthToken('valid_backend_jwt');

        final provider = OrderProvider(
          apiService: OrderApiService(client: syncClient),
          initialPrefs: prefs,
        );

        // Draft/invalid ID must not be recorded as a confirmed order
        provider.recordOrder(
          OrderModel(
            id: 0,
            userId: 7,
            status: 'pending',
            subtotal: 120.0,
            shippingFee: 0.0,
            total: 120.0,
            paymentMethod: 'Cash on Delivery (COD)',
            paymentStatus: 'unpaid',
            shippingAddress: 'Draft',
            createdAt: DateTime.now(),
          ),
        );
        expect(provider.orders, isEmpty);

        // Stale cached entry not present on backend is replaced upon fetchOrders
        provider.recordOrder(
          OrderModel(
            id: 99999,
            userId: 7,
            status: 'pending',
            subtotal: 120.0,
            shippingFee: 0.0,
            total: 120.0,
            paymentMethod: 'Cash on Delivery (COD)',
            paymentStatus: 'unpaid',
            shippingAddress: 'Stale local',
            createdAt: DateTime.now(),
          ),
        );
        expect(provider.orders.length, 1);

        await provider.fetchOrders();
        expect(provider.orders.map((o) => o.id).toList(), [900]);
      },
    );

    test(
      '5. Backend coupon failures never silently apply local demo vouchers (WELCOME10 / SAVE20)',
      () async {
        final failingCouponClient = ApiClient(
          client: checkoutClient((request) async {
            return http.Response(
              jsonEncode({
                'detail': 'Coupon service unavailable or invalid code',
              }),
              400,
            );
          }),
        );

        final cart = CartProvider(
          cartApiService: CartApiService(client: failingCouponClient),
        );
        cart.addItem(sampleProduct, quantity: 1); // $120.00

        for (final code in ['WELCOME10', 'SAVE20', 'SUPER50', 'SUMMER15']) {
          final applied = await cart.applyCoupon(code);
          expect(applied, isFalse, reason: 'Failed backend must reject $code');
          expect(cart.hasCoupon, isFalse);
          expect(cart.appliedCouponCode, isNull);
          expect(cart.discountAmount, 0.0);
          expect(cart.grandTotal, 120.0);
          expect(cart.couponErrorMessage, isNotNull);
        }
      },
    );

    test(
      'Verified backend coupon applies authoritative discount_amount in production mode',
      () async {
        final validCouponClient = ApiClient(
          client: checkoutClient((request) async {
            return http.Response(
              jsonEncode({
                'success': true,
                'message': 'Coupon applied',
                'data': {
                  'valid': true,
                  'code': 'WELCOME10',
                  'discount_type': 'percentage',
                  'discount_value': '10.00',
                  'discount_amount': '12.00',
                  'new_subtotal': '108.00',
                  'message': '10% discount verified by server',
                },
              }),
              200,
            );
          }),
        );

        final cart = CartProvider(
          cartApiService: CartApiService(client: validCouponClient),
        );
        cart.addItem(sampleProduct, quantity: 1); // $120.00

        final applied = await cart.applyCoupon('welcome10');
        expect(applied, isTrue);
        expect(cart.hasCoupon, isTrue);
        expect(cart.appliedCouponCode, 'WELCOME10');
        expect(cart.discountAmount, 12.0);
        expect(cart.grandTotal, 108.0);
      },
    );

    testWidgets(
      'Mobile checkout reuses durable key after screen disposal and recreation',
      (WidgetTester tester) async {
        SharedPreferences.setMockInitialValues({});
        final prefs = await SharedPreferences.getInstance();
        final orderProvider = OrderProvider(initialPrefs: prefs);
        final cartProvider = CartProvider();
        cartProvider.addItem(sampleProduct, quantity: 2);

        final capturedKeys = <String>[];
        final capturedHeaders = <String?>[];
        final capturedItems = <dynamic>[];
        var attemptCount = 0;

        final mockClient = ApiClient(
          client: checkoutClient((request) async {
            attemptCount++;
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            capturedKeys.add(body['idempotency_key'] as String);
            capturedHeaders.add(request.headers['Idempotency-Key']);
            capturedItems.add(body['items']);

            if (attemptCount == 1) {
              // First attempt: simulate temporary backend timeout/failure
              return http.Response(
                jsonEncode({'detail': 'Temporary network glitch'}),
                503,
              );
            }

            // Second attempt (retry): succeed
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'id': 991,
                  'user_id': 7,
                  'status': 'pending',
                  'subtotal': 240.0,
                  'discount_amount': 0.0,
                  'shipping_fee': 0.0,
                  'total': 240.0,
                  'payment_method': 'Cash on Delivery',
                  'payment_status': 'pending',
                  'shipping_address': 'Phnom Penh',
                  'created_at': '2026-10-31T10:00:00Z',
                  'items': [],
                },
              }),
              201,
            );
          }),
        )..setAuthToken('valid_backend_jwt');

        Widget checkoutWidget() => MultiProvider(
          providers: [
            ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
            ChangeNotifierProvider<OrderProvider>.value(value: orderProvider),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: CheckoutScreen(
              orderApiService: OrderApiService(client: mockClient),
            ),
          ),
        );
        await tester.pumpWidget(checkoutWidget());

        await tester.pumpAndSettle();

        // First attempt -> fails with 503
        await tester.tap(find.byKey(const Key('place_order_button')));
        await tester.pumpAndSettle();

        expect(attemptCount, 1);
        expect(find.byType(OrderSuccessScreen), findsNothing);
        expect(capturedKeys.length, 1);
        expect(capturedKeys.first.startsWith('mob_'), isTrue);
        expect(capturedHeaders.first, capturedKeys.first);
        expect(capturedItems.first, [
          {'product_id': 101, 'quantity': 2},
        ]);

        // Dispose the screen, then reopen it with a new provider/store instance.
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpWidget(checkoutWidget());
        await tester.pumpAndSettle();
        expect(find.text('Retry pending order'), findsOneWidget);
        await tester.tap(find.byKey(const Key('place_order_button')));
        await tester.pumpAndSettle();

        expect(attemptCount, 2);
        expect(capturedKeys.length, 2);
        // PROOF: The exact same idempotency key is submitted on the retry!
        expect(
          capturedKeys[1],
          capturedKeys[0],
          reason:
              'Retry must send the exact same idempotency key to prevent double charge',
        );
        expect(capturedHeaders[1], capturedKeys[0]);

        // Confirmed order reached
        expect(find.byType(OrderSuccessScreen), findsOneWidget);
        expect(orderProvider.orders.length, 1);
        expect(orderProvider.orders.first.id, 991);
        expect(cartProvider.isEmpty, isTrue);
      },
    );
  });
}
