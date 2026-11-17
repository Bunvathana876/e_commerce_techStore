import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/core/network/api_exceptions.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/checkout/providers/checkout_provider.dart';
import 'package:e_commerc_mobile_app/features/checkout/services/checkout_attempt_store.dart';
import 'package:e_commerc_mobile_app/features/orders/services/order_api_service.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';
import '../../support/checkout_api_fixture.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));
  const items = <Map<String, dynamic>>[
    {'product_id': 101, 'quantity': 1},
  ];
  http.Response response(dynamic data, [int status = 200]) =>
      http.Response(jsonEncode({'success': true, 'data': data}), status);
  Map<String, dynamic> confirmed({
    int userId = 7,
    String paymentStatus = 'pending',
  }) => {
    'id': 501,
    'user_id': userId,
    'status': 'delivered',
    'subtotal': 45,
    'shipping_fee': 2,
    'total': 47,
    'payment_method': 'Cash on Delivery',
    'payment_status': paymentStatus,
    'shipping_address': 'Test address',
    'created_at': '2026-11-17T00:00:00Z',
    'items': [],
  };
  CheckoutProvider provider(ApiClient client, {CheckoutAttemptStore? store}) =>
      CheckoutProvider(
        orders: OrderApiService(client: client),
        attempts: store,
      );

  test(
    'loads owned addresses and submits selected backend address ID and full contact details',
    () async {
      Map<String, dynamic>? sent;
      final client = ApiClient(
        client: checkoutClient((request) async {
          sent = jsonDecode(request.body) as Map<String, dynamic>;
          return response(confirmed(), 201);
        }),
      )..setAuthToken('user7');
      final checkout = provider(client);
      addTearDown(checkout.dispose);
      await checkout.load();
      expect(checkout.selectedAddress!.id, 1);
      checkout.select(checkout.addresses.last);
      await checkout.submit(items: items, paymentMethod: 'Cash on Delivery');
      expect(sent!['shipping_address_id'], 2);
      expect(sent!['shipping_address'], contains('Second Recipient'));
      expect(sent!['shipping_address'], contains('012345678'));
      expect(sent!['shipping_address'], contains('Test Province, 12000'));
      expect(sent!['items'], items);
      expect(sent!['idempotency_key'], startsWith('mob_'));
    },
  );

  test(
    'empty, failed and foreign address responses never produce a real order',
    () async {
      for (final mode in ['empty', 'failed', 'foreign']) {
        var orders = 0;
        final client = ApiClient(
          client: MockClient((request) async {
            if (request.url.path.endsWith('/auth/me')) {
              return response({'id': 7});
            }
            if (request.url.path.endsWith('/addresses')) {
              if (mode == 'failed') {
                return http.Response('{"detail":"Offline"}', 503);
              }
              return response(
                mode == 'empty' ? [] : [checkoutAddress(userId: 8)],
              );
            }
            orders++;
            return response(confirmed(), 201);
          }),
        )..setAuthToken('user7');
        final checkout = provider(client);
        await checkout.load();
        expect(checkout.selectedAddress, isNull);
        await expectLater(
          checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
          throwsA(isA<ApiException>()),
        );
        expect(orders, 0);
        checkout.dispose();
      }
    },
  );

  test(
    'failed address load can retry, and newly created address is selected',
    () async {
      var failLoad = true;
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/me')) return response({'id': 7});
          if (request.method == 'POST') {
            return response({
              ...checkoutAddress(id: 3),
              ...jsonDecode(request.body) as Map<String, dynamic>,
            }, 201);
          }
          if (failLoad) {
            return http.Response('{"detail":"Temporary failure"}', 503);
          }
          return response([]);
        }),
      )..setAuthToken('user7');
      final checkout = provider(client);
      addTearDown(checkout.dispose);
      await checkout.load();
      expect(checkout.error, isNotNull);
      failLoad = false;
      await checkout.load();
      expect(checkout.error, isNull);
      await checkout.addAddress({'full_name': 'New Recipient'});
      expect(checkout.selectedAddress!.id, 3);
      expect(checkout.selectedAddress!.recipientName, 'New Recipient');
    },
  );

  test(
    'lost response then restart reuses original payload/key and creates only one order',
    () async {
      final accepted = <String, Map<String, dynamic>>{};
      final sent = <Map<String, dynamic>>[];
      var loseResponse = true;
      final client = ApiClient(
        client: checkoutClient((request) async {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          sent.add(body);
          final key = body['idempotency_key'] as String;
          expect(request.headers['Idempotency-Key'], key);
          accepted.putIfAbsent(key, () => confirmed(paymentStatus: 'paid'));
          if (loseResponse) {
            loseResponse = false;
            throw http.ClientException('Response lost after server commit');
          }
          return response(accepted[key]);
        }),
      )..setAuthToken('user7');
      final first = provider(client);
      await first.load();
      await expectLater(
        first.submit(
          items: items,
          paymentMethod: 'Cash on Delivery',
          couponCode: 'ORIGINAL',
        ),
        throwsA(isA<ApiException>()),
      );
      final key = first.pending!.key;
      first.dispose();

      // New provider/store instances simulate a fresh screen/process reading disk.
      final restarted = provider(client);
      addTearDown(restarted.dispose);
      await restarted.load();
      expect(restarted.pending!.key, key);
      final order = await restarted.submit(
        items: [
          {'product_id': 202, 'quantity': 3},
        ],
        paymentMethod: 'Card',
        couponCode: 'CHANGED',
      );
      expect(order!.id, 501);
      expect(
        order.isPaid,
        isTrue,
        reason: 'Server-settled COD must remain paid on replay',
      );
      expect(
        sent[1],
        sent[0],
        reason: 'A pending request cannot silently change on retry',
      );
      expect(accepted, hasLength(1));
      await restarted.acknowledge();
      expect(await CheckoutAttemptStore().read(7), isNull);
      await restarted.submit(items: items, paymentMethod: 'Cash on Delivery');
      expect(
        accepted,
        hasLength(2),
        reason: 'A later intentional purchase gets a fresh key',
      );
    },
  );

  test(
    'pending attempts are isolated by account and survive logout/relogin of original owner',
    () async {
      final store = CheckoutAttemptStore();
      final original = await store.prepare(7, {'items': items});
      expect(await CheckoutAttemptStore().read(8), isNull);
      final other = await store.prepare(8, {'items': items});
      expect(other.key, isNot(original.key));
      expect((await CheckoutAttemptStore().read(7))!.key, original.key);
      await store.complete(8, other.key);
      expect((await store.read(7))!.key, original.key);
    },
  );

  test(
    'late address and order responses cannot populate a different session',
    () async {
      final addressResponse = Completer<http.Response>();
      final client = ApiClient(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/me')) return response({'id': 7});
          return addressResponse.future;
        }),
      )..setAuthToken('user7');
      final checkout = provider(client);
      addTearDown(checkout.dispose);
      final loading = checkout.load();
      await Future<void>.delayed(Duration.zero);
      client.setAuthToken('user8');
      addressResponse.complete(response([checkoutAddress()]));
      await loading;
      expect(checkout.addresses, isEmpty);
      expect(checkout.sessionCurrent, isFalse);
      await expectLater(
        checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
        throwsA(isA<ApiException>()),
      );

      final orderResponse = Completer<http.Response>();
      final secondClient = ApiClient(
        client: checkoutClient((_) => orderResponse.future),
      )..setAuthToken('user7');
      final second = provider(secondClient);
      addTearDown(second.dispose);
      await second.load();
      final submission = second.submit(
        items: items,
        paymentMethod: 'Cash on Delivery',
      );
      final expectation = expectLater(submission, throwsA(isA<ApiException>()));
      await Future<void>.delayed(Duration.zero);
      secondClient.setAuthToken('user8');
      orderResponse.complete(response(confirmed()));
      await expectation;
      expect(await CheckoutAttemptStore().read(7), isNotNull);
      expect(await CheckoutAttemptStore().read(8), isNull);
    },
  );

  test(
    'storage failure sends no order; corrupt or expired retry state fails closed',
    () async {
      var sent = 0;
      var failStorage = false;
      final store = CheckoutAttemptStore(
        preferences: () async {
          if (failStorage) throw StateError('Unavailable');
          return SharedPreferences.getInstance();
        },
      );
      final client = ApiClient(
        client: checkoutClient((_) async {
          sent++;
          return response(confirmed());
        }),
      )..setAuthToken('user7');
      final checkout = provider(client, store: store);
      addTearDown(checkout.dispose);
      await checkout.load();
      failStorage = true;
      await expectLater(
        checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
        throwsA(isA<StateError>()),
      );
      expect(sent, 0);
      failStorage = false;
      await store.prepare(7, {'items': items});
      final prefs = await SharedPreferences.getInstance();
      final storageKey = prefs.getKeys().singleWhere(
        (key) => key.startsWith('checkout_pending_'),
      );
      final data =
          jsonDecode(prefs.getString(storageKey)!) as Map<String, dynamic>;
      data['created_at'] = DateTime.now()
          .subtract(const Duration(days: 2))
          .toIso8601String();
      await prefs.setString(storageKey, jsonEncode(data));
      await checkout.load();
      await expectLater(
        checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
        throwsA(isA<ApiException>()),
      );
      expect(sent, 0);
      await prefs.setString(storageKey, '{invalid');
      await checkout.load();
      expect(checkout.error, contains('could not be restored'));
      await expectLater(
        checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
        throwsA(isA<ApiException>()),
      );
      expect(sent, 0);
    },
  );

  test(
    'definitive rejection releases pending request so customer can correct it',
    () async {
      final client = ApiClient(
        client: checkoutClient(
          (_) async => http.Response('{"detail":"Out of stock"}', 400),
        ),
      )..setAuthToken('user7');
      final checkout = provider(client);
      addTearDown(checkout.dispose);
      await checkout.load();
      await expectLater(
        checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
        throwsA(isA<ApiException>()),
      );
      expect(checkout.pending, isNull);
      expect(await CheckoutAttemptStore().read(7), isNull);
    },
  );

  test(
    'simultaneous store instances reserve one key for the same customer',
    () async {
      final attempts = await Future.wait([
        CheckoutAttemptStore().prepare(7, {'items': items}),
        CheckoutAttemptStore().prepare(7, {'items': items}),
      ]);
      expect(attempts[0].key, attempts[1].key);
    },
  );

  test(
    'stock conflicts release a rejected checkout but processing conflicts retain its key',
    () async {
      for (final detail in [
        "Insufficient stock for 'Test'. Available: 0, requested: 1.",
        'A checkout request with this idempotency key is currently processing. Please wait.',
      ]) {
        SharedPreferences.setMockInitialValues({});
        final client = ApiClient(
          client: checkoutClient(
            (_) async => http.Response(jsonEncode({'detail': detail}), 409),
          ),
        )..setAuthToken('user7');
        final checkout = provider(client);
        await checkout.load();
        await expectLater(
          checkout.submit(items: items, paymentMethod: 'Cash on Delivery'),
          throwsA(isA<ApiException>()),
        );
        if (detail.startsWith('Insufficient')) {
          expect(checkout.pending, isNull);
          expect(await CheckoutAttemptStore().read(7), isNull);
        } else {
          expect(checkout.pending, isNotNull);
          expect(
            (await CheckoutAttemptStore().read(7))!.key,
            checkout.pending!.key,
          );
        }
        checkout.dispose();
      }
    },
  );

  test(
    'standard shipping matches backend boundaries before coupon discounts',
    () async {
      for (final amount in [45.0, 99.99, 100.0, 120.0]) {
        final cart = CartProvider(useRemoteBackend: false);
        cart.addItem(
          ProductModel(
            id: 1,
            name: 'Test',
            description: '',
            price: amount,
            rating: 0,
            reviewCount: 0,
            categoryId: 1,
            imageUrl: '',
          ),
        );
        final fee = amount >= 100 ? 0.0 : 2.0;
        expect(cart.shippingFee, fee);
        expect(cart.grandTotal, amount + fee);
        await cart.applyCoupon('WELCOME10');
        expect(cart.shippingFee, fee);
        expect(
          cart.grandTotal,
          closeTo(amount - cart.discountAmount + fee, .001),
        );
        cart.dispose();
      }
    },
  );
}
