import 'package:flutter/foundation.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_exceptions.dart';
import '../../auth/providers/auth_provider.dart';
import '../../orders/models/order_model.dart';
import '../../orders/services/order_api_service.dart';
import '../models/address_model.dart';
import '../services/address_service.dart';
import '../services/checkout_attempt_store.dart';
import '../services/stripe_payment_gateway.dart';

class CheckoutProvider extends ChangeNotifier {
  final OrderApiService orders;
  final AddressService _addresses;
  final CheckoutAttemptStore _attempts;
  final StripePaymentGateway _stripeGateway;
  bool _disposed = false;
  int? _authEpoch;
  int? _userId;
  bool isLoading = false;
  bool isSubmitting = false;
  bool cardGatewayChecked = false;
  bool cardGatewayConfigured = false;
  bool enableCardPayment = true;
  bool enableCodPayment = true;
  String? stripePublishableKey;
  String? error;
  List<AddressModel> addresses = [];
  AddressModel? selectedAddress;
  CheckoutAttempt? pending;

  CheckoutProvider({
    required this.orders,
    CheckoutAttemptStore? attempts,
    StripePaymentGateway? stripeGateway,
  }) : _addresses = AddressService(client: orders.client),
       _attempts = attempts ?? CheckoutAttemptStore(),
       _stripeGateway = stripeGateway ?? const FlutterStripePaymentGateway() {
    AuthProvider.registerLogoutListener(_clearSession);
  }

  bool get sessionCurrent =>
      !_disposed &&
      orders.client.isAuthenticated &&
      _authEpoch == orders.client.authEpoch;

  void _checkSession() {
    if (!sessionCurrent) {
      _clearSession();
      throw const ApiException(
        'Your session changed. Please reopen checkout after signing in.',
      );
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _clearSession() {
    _authEpoch = null;
    _userId = null;
    cardGatewayChecked = false;
    cardGatewayConfigured = false;
    enableCardPayment = true;
    enableCodPayment = true;
    stripePublishableKey = null;
    addresses = [];
    selectedAddress = null;
    pending = null;
    error = 'Please sign in to place an order.';
    _notify();
  }

  Future<void> refreshPaymentsConfig() => _refreshPaymentsConfig();

  Future<void> _refreshPaymentsConfig() async {
    try {
      final cfg = await orders.client.get<Map<String, dynamic>>(
        ApiEndpoints.paymentsConfig,
        parser: (data) =>
            data is Map ? Map<String, dynamic>.from(data) : <String, dynamic>{},
      );
      _checkSession();
      enableCardPayment = cfg.data?['enable_card_payment'] != false;
      enableCodPayment = cfg.data?['enable_cod_payment'] != false;
      cardGatewayConfigured =
          enableCardPayment && cfg.data?['card_gateway_configured'] == true;
      stripePublishableKey = cfg.data?['stripe_publishable_key']?.toString();
      cardGatewayChecked = true;
    } catch (e) {
      if (e is ApiException && e.message.startsWith('Your session changed')) {
        rethrow;
      }
      cardGatewayConfigured = false;
      stripePublishableKey = null;
      cardGatewayChecked = true;
    }
  }

  Future<void> load() async {
    if (isLoading || isSubmitting) return;
    isLoading = true;
    error = null;
    addresses = [];
    selectedAddress = null;
    pending = null;
    _authEpoch = orders.client.authEpoch;
    _notify();
    try {
      if (!orders.client.isAuthenticated) {
        throw const ApiException('Please sign in to place an order.');
      }
      final userId = await _addresses.currentUserId();
      _checkSession();
      _userId = userId;
      final attempt = await _attempts.read(userId);
      _checkSession();
      pending = attempt;
      final loaded = await _addresses.list(userId);
      _checkSession();
      addresses = loaded;
      selectedAddress =
          loaded.where((address) => address.isDefault).firstOrNull ??
          loaded.firstOrNull;
    } catch (e) {
      if (!_disposed) {
        error = e is ApiException
            ? e.message
            : 'Unable to load checkout. Please retry.';
      }
    } finally {
      isLoading = false;
      _notify();
    }
  }

  void select(AddressModel address) {
    _checkSession();
    if (isSubmitting || pending != null || !addresses.contains(address)) return;
    selectedAddress = address;
    _notify();
  }

  Future<void> addAddress(Map<String, dynamic> data) async {
    _checkSession();
    if (_userId == null || isSubmitting || pending != null) return;
    final saved = await _addresses.create(_userId!, data);
    _checkSession();
    addresses = [...addresses, saved];
    selectedAddress = saved;
    error = null;
    _notify();
  }

  Future<OrderModel?> submit({
    required List<Map<String, dynamic>> items,
    required String paymentMethod,
    String? couponCode,
  }) async {
    if (isSubmitting || isLoading) return null;
    _checkSession();
    if (_userId == null || (error != null && pending == null)) {
      throw const ApiException('Reload checkout before placing an order.');
    }
    isSubmitting = true;
    _notify();
    try {
      if (pending == null) {
        final address = selectedAddress;
        if (address == null) {
          throw const ApiException('Add or select your delivery address.');
        }
        if (items.isEmpty) {
          throw const ApiException('Cannot place order with an empty cart');
        }
        final normalizedMethod = paymentMethod.trim().toLowerCase();
        final isCod = normalizedMethod.contains('cash') || normalizedMethod == 'cod';
        final isCard = normalizedMethod.contains('card');
        if (!isCod && !isCard) {
          throw const ApiException(
            'Unsupported payment method. Only Credit / Debit Card and Cash on Delivery are supported.',
          );
        }
        if (isCod && cardGatewayChecked && !enableCodPayment) {
          throw const ApiException(
            'Cash on Delivery is currently disabled in store settings.',
          );
        }
        if (isCard) {
          await _refreshPaymentsConfig();
          if (!enableCardPayment) {
            throw const ApiException(
              'Credit / Debit Card payments are currently disabled in store settings.',
            );
          }
          if (!cardGatewayConfigured) {
            throw const ApiException(
              'Online card payments are not available right now. Please select Cash on Delivery.',
            );
          }
        }
        final attempt = await _attempts.prepare(_userId!, {
          'shipping_address_id': address.id,
          'shipping_address': address.fullAddress,
          'payment_method': paymentMethod,
          'coupon_code': ?couponCode,
          'items': items,
        });
        _checkSession();
        pending = attempt;
      }
      final attempt = pending!;
      if (!attempt.canRetry) {
        throw const ApiException(
          'This checkout is too old to retry safely. Check your orders or contact support before placing another order.',
        );
      }
      _notify();
      final request = attempt.request;
      final order = await orders.createOrder(
        shippingAddress: request['shipping_address'] as String,
        shippingAddressId: request['shipping_address_id'] as int?,
        paymentMethod: request['payment_method'] as String,
        couponCode: request['coupon_code'] as String?,
        items: attempt.items,
        idempotencyKey: attempt.key,
      );
      _checkSession();
      if (order.userId != _userId) {
        throw const ApiException('Could not verify order ownership.');
      }

      final effectiveMethod =
          (request['payment_method']?.toString() ?? order.paymentMethod)
              .trim()
              .toLowerCase();
      final requiresCardSettlement =
          effectiveMethod.contains('card') && !order.isPaid;

      if (requiresCardSettlement) {
        await _refreshPaymentsConfig();
        if (!cardGatewayConfigured) {
          throw const ApiException(
            'Online card payments are not available right now. Please select Cash on Delivery.',
          );
        }

        final intentRes = await orders.client.post<CardPaymentIntentSession>(
          ApiEndpoints.paymentCardIntent,
          body: {'order_id': order.id},
          parser: (data) => CardPaymentIntentSession.fromJson(
            data is Map ? Map<String, dynamic>.from(data) : <String, dynamic>{},
          ),
        );
        _checkSession();

        final intent = intentRes.data;
        final publishableKey =
            (intent != null && intent.publishableKey.isNotEmpty)
            ? intent.publishableKey
            : (stripePublishableKey ?? '');
        if (intent == null ||
            intent.paymentIntentId.isEmpty ||
            intent.clientSecret.isEmpty ||
            publishableKey.isEmpty) {
          throw const ApiException(
            'Unable to initialize Stripe card payment session for this order.',
          );
        }

        try {
          await _stripeGateway.presentCardPaymentSheet(
            publishableKey: publishableKey,
            clientSecret: intent.clientSecret,
          );
        } on StripePaymentSheetException catch (e) {
          throw ApiException(e.message);
        }
        _checkSession();

        await orders.client.post<Map<String, dynamic>>(
          ApiEndpoints.paymentCardConfirm,
          body: {
            'order_id': order.id,
            'payment_intent_id': intent.paymentIntentId,
          },
          parser: (data) => data is Map
              ? Map<String, dynamic>.from(data)
              : <String, dynamic>{},
        );
        _checkSession();

        return order.copyWith(paymentStatus: 'paid');
      }

      return order;
    } on ApiException catch (e) {
      // These responses definitively reject the request. Timeouts, 5xx and
      // processing conflicts stay durable until the original result is known.
      final rejectedInventory =
          e.statusCode == 409 &&
          (e.message.startsWith('Insufficient stock for ') ||
              e.message.startsWith('Inventory changed concurrently for '));
      if (sessionCurrent &&
          pending != null &&
          ([400, 422].contains(e.statusCode) || rejectedInventory)) {
        await _attempts.complete(_userId!, pending!.key);
        _checkSession();
        pending = null;
      }
      rethrow;
    } finally {
      isSubmitting = false;
      _notify();
    }
  }

  Future<void> acknowledge() async {
    _checkSession();
    final attempt = pending;
    if (attempt == null) return;
    await _attempts.complete(_userId!, attempt.key);
    _checkSession();
    pending = null;
    _notify();
  }

  @override
  void dispose() {
    _disposed = true;
    AuthProvider.unregisterLogoutListener(_clearSession);
    super.dispose();
  }
}
