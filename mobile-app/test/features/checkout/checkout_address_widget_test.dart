import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/checkout/screens/checkout_screen.dart';
import 'package:e_commerc_mobile_app/features/orders/services/order_api_service.dart';
import '../../support/checkout_api_fixture.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  Widget screen(ApiClient client, CartProvider cart, {bool dark = false}) =>
      ChangeNotifierProvider<CartProvider>.value(
        value: cart,
        child: MaterialApp(
          theme: dark ? AppTheme.darkTheme : AppTheme.lightTheme,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(1.3)),
            child: child!,
          ),
          home: CheckoutScreen(
            orderApiService: OrderApiService(client: client),
          ),
        ),
      );

  for (final dark in [false, true]) {
    testWidgets(
      'real address form validates, retains failed input and saves on a narrow ${dark ? "dark" : "light"} screen',
      (tester) async {
        tester.view.physicalSize = const Size(320, 850);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        var saves = 0;
        Map<String, dynamic>? saved;
        final client = ApiClient(
          client: MockClient((request) async {
            if (request.url.path.endsWith('/auth/me')) {
              return http.Response('{"success":true,"data":{"id":7}}', 200);
            }
            if (request.method == 'GET') {
              return http.Response('{"success":true,"data":[]}', 200);
            }
            expect(request.url.path, '/api/v1/addresses');
            expect(request.headers['Authorization'], 'Bearer test-user');
            saves++;
            saved = jsonDecode(request.body) as Map<String, dynamic>;
            if (saves == 1) {
              return http.Response(
                '{"detail":"Unable to save right now"}',
                503,
              );
            }
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {...checkoutAddress(), ...saved!},
              }),
              201,
            );
          }),
        )..setAuthToken('test-user');
        final cart = CartProvider();
        addTearDown(cart.dispose);
        await tester.pumpWidget(screen(client, cart, dark: dark));
        await tester.pumpAndSettle();
        expect(find.textContaining('No saved addresses'), findsOneWidget);
        expect(find.text('Bun Vathana'), findsNothing);
        await tester.tap(find.byKey(const Key('add_address_button')));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Save address'));
        await tester.pumpAndSettle();
        expect(find.text('Required'), findsWidgets);
        expect(saves, 0);
        for (final entry in {
          'full_name': 'Customer Example',
          'phone': '012345678',
          'address_line': 'Actual street',
          'city': 'Actual city',
        }.entries) {
          final field = find.byKey(Key('address_${entry.key}'));
          await tester.ensureVisible(field);
          await tester.enterText(field, entry.value);
        }
        await tester.tap(find.text('Save address'));
        await tester.pumpAndSettle();
        expect(
          find.text('Server encountered an error. Please try again later.'),
          findsOneWidget,
        );
        expect(find.text('Customer Example'), findsOneWidget);
        await tester.tap(find.text('Save address'));
        await tester.pumpAndSettle();
        expect(saves, 2);
        expect(saved!['full_name'], 'Customer Example');
        expect(saved!['is_default'], isTrue);
        expect(find.text('Add delivery address'), findsNothing);
        expect(find.text('Customer Example'), findsOneWidget);
        expect(find.textContaining('Actual street'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets(
    'address loading and failure offer a successful retry without fake addresses',
    (tester) async {
      final loading = Completer<http.Response>();
      var addressRequests = 0;
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/me')) {
            return http.Response('{"data":{"id":7}}', 200);
          }
          addressRequests++;
          if (addressRequests == 1) return loading.future;
          return http.Response(
            jsonEncode({
              'data': [checkoutAddress()],
            }),
            200,
          );
        }),
      )..setAuthToken('test-user');
      final cart = CartProvider();
      addTearDown(cart.dispose);
      await tester.pumpWidget(screen(client, cart));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      loading.complete(
        http.Response('{"detail":"Address service offline"}', 503),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Server encountered an error. Please try again later.'),
        findsOneWidget,
      );
      expect(find.text('Test Customer'), findsNothing);
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(addressRequests, 2);
      expect(find.text('Test Customer'), findsOneWidget);
    },
  );
}
