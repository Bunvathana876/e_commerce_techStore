import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../../core/network/api_exceptions.dart';
import '../../auth/providers/auth_provider.dart';
import '../../products/models/product_model.dart';
import '../models/cart_item_model.dart';
import '../services/cart_api_service.dart';

class CartProvider extends ChangeNotifier {
  final CartApiService _cartApiService;
  final bool useRemoteBackend;
  final List<CartItemModel> _items = [];
  bool _isLoading = false;
  int _sessionEpoch = 0;

  // Coupon / Promo Code State
  String? _appliedCouponCode;
  double _discountAmount = 0.0;
  String? _couponErrorMessage;
  String? _couponSuccessMessage;
  bool _isApplyingCoupon = false;

  bool get isLoading => _isLoading;
  bool get isApplyingCoupon => _isApplyingCoupon;
  String? get appliedCouponCode => _appliedCouponCode;
  double get discountAmount => _discountAmount;
  String? get couponErrorMessage => _couponErrorMessage;
  String? get couponSuccessMessage => _couponSuccessMessage;
  bool get hasCoupon => _appliedCouponCode != null && _discountAmount > 0;
  int get sessionEpoch => _sessionEpoch;

  CartProvider({
    CartApiService? cartApiService,
    this.useRemoteBackend = true,
  }) : _cartApiService = cartApiService ?? CartApiService() {
    AuthProvider.registerLogoutListener(clearCart);
  }

  // Read-only list of items in the cart
  List<CartItemModel> get items => List.unmodifiable(_items);

  // Check if cart has zero items
  bool get isEmpty => _items.isEmpty;

  // Total quantity of all units in the cart
  int get totalItemsCount => _items.fold(0, (sum, item) => sum + item.quantity);

  // Subtotal before shipping fees
  double get subtotal => _items.fold(0.0, (sum, item) => sum + item.totalPrice);

  // Match backend checkout: free at $100 before discounts, otherwise $2.
  double get shippingFee => (subtotal >= 100.0 || _items.isEmpty) ? 0.0 : 2.0;

  // Final grand total (subtotal - discount + shipping)
  double get grandTotal {
    final raw = (subtotal - _discountAmount) + shippingFee;
    return raw < 0.0 ? 0.0 : raw;
  }

  // Pre-configured commercial vouchers fallback for offline/instant evaluation
  static final Map<String, Map<String, dynamic>> _demoVouchers = {
    'WELCOME10': {
      'type': 'percent',
      'value': 10.0,
      'min': 0.0,
      'max': 100.0,
      'name': '10% Welcome Discount',
    },
    'SAVE20': {
      'type': 'fixed',
      'value': 20.0,
      'min': 50.0,
      'max': null,
      'name': '\$20 Order Discount',
    },
    'SUPER50': {
      'type': 'fixed',
      'value': 50.0,
      'min': 150.0,
      'max': null,
      'name': '\$50 Super Discount',
    },
    'SUMMER15': {
      'type': 'percent',
      'value': 15.0,
      'min': 30.0,
      'max': 75.0,
      'name': '15% Summer Sale',
    },
  };

  // Re-evaluate discount if cart contents changed
  void _recalculateCouponIfApplied() {
    if (_appliedCouponCode == null) return;
    if (_items.isEmpty || subtotal <= 0) {
      _appliedCouponCode = null;
      _discountAmount = 0.0;
      _couponErrorMessage = null;
      _couponSuccessMessage = null;
      return;
    }

    if (!useRemoteBackend) {
      _calculateLocalDiscount(_appliedCouponCode!, subtotal, silent: true);
      return;
    }

    if (_discountAmount > subtotal) {
      _discountAmount = subtotal;
    }
    unawaited(_revalidateAppliedCoupon(_appliedCouponCode!));
  }

  Future<void> _revalidateAppliedCoupon(String code) async {
    final requestEpoch = _sessionEpoch;
    try {
      final dataMap = await _cartApiService.validateCoupon(
        code: code,
        subtotal: subtotal,
      );
      if (requestEpoch != _sessionEpoch || _appliedCouponCode != code || _items.isEmpty) return;

      final amt = _parseAmount(dataMap['discount_amount']);
      if (dataMap['valid'] == true && amt > 0) {
        _discountAmount = amt > subtotal ? subtotal : amt;
        _couponErrorMessage = null;
      } else {
        _appliedCouponCode = null;
        _discountAmount = 0.0;
        _couponSuccessMessage = null;
        _couponErrorMessage = dataMap['message']?.toString();
      }
      notifyListeners();
    } catch (e) {
      if (requestEpoch != _sessionEpoch || _appliedCouponCode != code) return;
      _appliedCouponCode = null;
      _discountAmount = 0.0;
      _couponSuccessMessage = null;
      _couponErrorMessage = e is ApiException
          ? e.message
          : 'Promo code could not be re-verified.';
      notifyListeners();
    }
  }

  static double _parseAmount(dynamic raw) {
    if (raw is num) return raw.toDouble();
    if (raw is String) return double.tryParse(raw) ?? 0.0;
    return 0.0;
  }

  bool _calculateLocalDiscount(
    String code,
    double currentSubtotal, {
    bool silent = false,
  }) {
    final upper = code.trim().toUpperCase();
    final voucher = _demoVouchers[upper];

    if (voucher == null) {
      if (!silent) {
        _couponErrorMessage = "Promo code '$upper' does not exist.";
        _couponSuccessMessage = null;
      }
      return false;
    }

    final double minSpend = (voucher['min'] as num).toDouble();
    if (currentSubtotal < minSpend) {
      if (!silent) {
        _couponErrorMessage =
            "Promo code '$upper' requires a minimum order of \$${minSpend.toStringAsFixed(2)}.";
        _couponSuccessMessage = null;
      }
      return false;
    }

    double computed = 0.0;
    if (voucher['type'] == 'percent') {
      final double pct = (voucher['value'] as num).toDouble();
      computed = (currentSubtotal * pct) / 100.0;
      final maxDisc = voucher['max'];
      if (maxDisc != null && computed > (maxDisc as num).toDouble()) {
        computed = (maxDisc).toDouble();
      }
    } else {
      computed = (voucher['value'] as num).toDouble();
    }

    if (computed > currentSubtotal) {
      computed = currentSubtotal;
    }

    _appliedCouponCode = upper;
    _discountAmount = double.parse(computed.toStringAsFixed(2));
    _couponErrorMessage = null;
    _couponSuccessMessage =
        "Promo code '$upper' applied! Saved \$${_discountAmount.toStringAsFixed(2)}.";
    return true;
  }

  // Apply a promotional coupon code
  Future<bool> applyCoupon(String code) async {
    final cleanCode = code.trim().toUpperCase();
    if (cleanCode.isEmpty) {
      _couponErrorMessage = 'Please enter a promo code.';
      _couponSuccessMessage = null;
      notifyListeners();
      return false;
    }

    if (_items.isEmpty) {
      _couponErrorMessage = 'Your cart is empty.';
      _couponSuccessMessage = null;
      notifyListeners();
      return false;
    }

    _isApplyingCoupon = true;
    _couponErrorMessage = null;
    notifyListeners();

    if (!useRemoteBackend) {
      final localResult = _calculateLocalDiscount(cleanCode, subtotal);
      _isApplyingCoupon = false;
      notifyListeners();
      return localResult;
    }

    try {
      final dataMap = await _cartApiService.validateCoupon(
        code: cleanCode,
        subtotal: subtotal,
      );
      final amt = _parseAmount(dataMap['discount_amount']);
      if (dataMap['valid'] == true && amt > 0) {
        final resolvedCode = dataMap['code']?.toString().trim();
        _appliedCouponCode = (resolvedCode != null && resolvedCode.isNotEmpty)
            ? resolvedCode.toUpperCase()
            : cleanCode;
        _discountAmount = amt > subtotal ? subtotal : amt;
        _couponSuccessMessage =
            dataMap['message']?.toString() ??
            "Promo code '$_appliedCouponCode' applied! Saved \$${_discountAmount.toStringAsFixed(2)}.";
        _couponErrorMessage = null;
        _isApplyingCoupon = false;
        notifyListeners();
        return true;
      }

      _appliedCouponCode = null;
      _discountAmount = 0.0;
      _couponSuccessMessage = null;
      _couponErrorMessage =
          dataMap['message']?.toString() ??
          "Promo code '$cleanCode' is not valid.";
      _isApplyingCoupon = false;
      notifyListeners();
      return false;
    } catch (e) {
      _appliedCouponCode = null;
      _discountAmount = 0.0;
      _couponSuccessMessage = null;
      _couponErrorMessage = e is ApiException
          ? e.message
          : 'Unable to validate promo code. Please try again.';
      _isApplyingCoupon = false;
      notifyListeners();
      return false;
    }
  }

  // Remove the currently applied coupon
  void removeCoupon() {
    _appliedCouponCode = null;
    _discountAmount = 0.0;
    _couponErrorMessage = null;
    _couponSuccessMessage = null;
    notifyListeners();
  }

  // Fetch cart from remote API when logged in
  Future<void> loadRemoteCart() async {
    if (!_cartApiService.client.isAuthenticated) return;
    final requestEpoch = _sessionEpoch;
    _isLoading = true;
    notifyListeners();
    try {
      final remoteItems = await _cartApiService.getCart();
      if (requestEpoch != _sessionEpoch) return;
      _items.clear();
      _items.addAll(remoteItems);
      _recalculateCouponIfApplied();
    } catch (e) {
      debugPrint('CartProvider loadRemoteCart note: $e');
    } finally {
      if (requestEpoch == _sessionEpoch) {
        _isLoading = false;
        notifyListeners();
      }
    }
  }

  // Add a product or increase its quantity if matching variant exists
  void addItem(
    ProductModel product, {
    String variant = 'Standard',
    int quantity = 1,
  }) {
    final existingIndex = _items.indexWhere(
      (item) => item.product.id == product.id && item.variant == variant,
    );

    if (existingIndex >= 0) {
      _items[existingIndex].quantity += quantity;
    } else {
      _items.add(
        CartItemModel(product: product, variant: variant, quantity: quantity),
      );
    }
    _recalculateCouponIfApplied();
    notifyListeners();

    // Sync with backend if authenticated
    if (_cartApiService.client.isAuthenticated) {
      _cartApiService
          .addToCart(
            productId: product.id,
            quantity: quantity,
            variant: variant,
          )
          .catchError((e) {
            debugPrint('Failed to sync added cart item with backend: $e');
            return CartItemModel(product: product);
          });
    }
  }

  // Increase quantity of item by 1
  void incrementQuantity(int index) {
    if (index >= 0 && index < _items.length) {
      _items[index].quantity++;
      final item = _items[index];
      _recalculateCouponIfApplied();
      notifyListeners();

      if (_cartApiService.client.isAuthenticated) {
        _cartApiService
            .updateQuantity(productId: item.product.id, quantity: item.quantity)
            .catchError((e) {
              debugPrint('Failed to sync incremented cart item: $e');
            });
      }
    }
  }

  // Decrease quantity by 1, or remove item if quantity reaches 0
  void decrementQuantity(int index) {
    if (index >= 0 && index < _items.length) {
      final item = _items[index];
      if (_items[index].quantity > 1) {
        _items[index].quantity--;
        _recalculateCouponIfApplied();
        notifyListeners();

        if (_cartApiService.client.isAuthenticated) {
          _cartApiService
              .updateQuantity(
                productId: item.product.id,
                quantity: item.quantity,
              )
              .catchError((e) {
                debugPrint('Failed to sync decremented cart item: $e');
              });
        }
      } else {
        _items.removeAt(index);
        _recalculateCouponIfApplied();
        notifyListeners();

        if (_cartApiService.client.isAuthenticated) {
          _cartApiService.removeFromCart(item.product.id).catchError((e) {
            debugPrint('Failed to sync removed cart item: $e');
          });
        }
      }
    }
  }

  // Remove item completely from cart
  void removeItem(int index) {
    if (index >= 0 && index < _items.length) {
      final item = _items.removeAt(index);
      _recalculateCouponIfApplied();
      notifyListeners();

      if (_cartApiService.client.isAuthenticated) {
        _cartApiService.removeFromCart(item.product.id).catchError((e) {
          debugPrint('Failed to sync removed cart item: $e');
        });
      }
    }
  }

  // Empty the entire cart (e.g. after successful order placement or logout)
  void clearCart() {
    _sessionEpoch++;
    _items.clear();
    _appliedCouponCode = null;
    _discountAmount = 0.0;
    _couponErrorMessage = null;
    _couponSuccessMessage = null;
    notifyListeners();
  }

  @override
  void dispose() {
    AuthProvider.unregisterLogoutListener(clearCart);
    super.dispose();
  }
}
