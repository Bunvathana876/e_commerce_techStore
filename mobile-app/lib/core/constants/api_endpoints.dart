import 'dart:io' show Platform;
import 'package:flutter/foundation.dart';

// Central configuration for API endpoints and network settings
class ApiEndpoints {
  // Prevent instantiation
  ApiEndpoints._();

  // Active base URL for network requests
  static String _customBaseUrl = '';
  static const String _envBaseUrl = String.fromEnvironment('API_URL');

  // Get current base URL according to platform or custom setting
  static String get baseUrl {
    if (_customBaseUrl.isNotEmpty) {
      return _customBaseUrl;
    }

    if (_envBaseUrl.isNotEmpty) {
      return validateBaseUrl(_envBaseUrl);
    }

    if (kReleaseMode) {
      throw StateError('Release builds require an HTTPS API_URL.');
    }

    if (kIsWeb) {
      return 'http://localhost:8000';
    }

    try {
      if (Platform.isAndroid) {
        // Standard Android emulator loopback alias to host machine
        return 'http://10.0.2.2:8000';
      }
    } catch (_) {
      // In case Platform check is unavailable
    }

    // Default for iOS simulator, macOS, and desktop
    return 'http://localhost:8000';
  }

  // Override base URL at runtime (e.g. for real device testing with local Wi-Fi IP)
  static void setBaseUrl(String url) {
    _customBaseUrl = validateBaseUrl(url);
  }

  // Endpoint constants already include /api/v1, so only an origin is valid.
  static String validateBaseUrl(
    String url, {
    bool requireHttps = kReleaseMode,
  }) {
    final uri = Uri.tryParse(url.trim());
    if (uri == null ||
        !uri.hasAuthority ||
        uri.host.isEmpty ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/')) {
      throw ArgumentError('API_URL must be an HTTP(S) origin without a path.');
    }
    if (requireHttps &&
        (uri.scheme != 'https' ||
            uri.host == 'localhost' ||
            uri.host.endsWith('.localhost') ||
            uri.host.startsWith('127.') ||
            ['0.0.0.0', '::1', '10.0.2.2'].contains(uri.host))) {
      throw ArgumentError('Release API_URL must use HTTPS and a remote host.');
    }
    return uri.origin;
  }

  // Reset base URL to platform defaults
  static void resetBaseUrl() {
    _customBaseUrl = '';
  }

  // Seeded database images mapped to verified high-resolution CDN assets
  static const Map<String, String> _seededImageMap = {
    'assets/images/products/nike_airmax.png':
        'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/adidas_ultraboost.png':
        'https://images.unsplash.com/photo-1608231387042-66d1773070a5?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/puma_rsx.png':
        'https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/new_balance.png':
        'https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/sony_headphones.png':
        'https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/apple_watch.png':
        'https://images.unsplash.com/photo-1546868871-7041f2a55e12?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/galaxy_buds.png':
        'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/denim_jacket.png':
        'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/fleece_hoodie.png':
        'https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/chinos.png':
        'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/leather_wallet.png':
        'https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=85',
    'assets/images/products/face_oil.png':
        'https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=900&q=85',
    // Categories seeded in DB
    'assets/images/products/shoe.png':
        'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=600&q=80',
    'assets/images/products/headphone.png':
        'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=600&q=80',
    'assets/images/products/hoodie.png':
        'https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?auto=format&fit=crop&w=600&q=80',
    'assets/images/products/watch.png':
        'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=600&q=80',
    'assets/images/products/skincare.png':
        'https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=600&q=80',
  };

  // Normalize image URLs returned by the backend or database
  static String normalizeImageUrl(String? url, {String? fallbackName}) {
    if (url == null || url.trim().isEmpty) {
      if (fallbackName != null && fallbackName.isNotEmpty) {
        return _resolveByName(fallbackName);
      }
      return '';
    }
    final trimmed = url.trim();

    // Check if it's one of the known seeded database asset references
    if (_seededImageMap.containsKey(trimmed)) {
      return _seededImageMap[trimmed]!;
    }

    // Replace obsolete or dead ephemeral tunnel hosts
    if (trimmed.contains('trycloudflare.com')) {
      return 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80';
    }

    // Already a complete external URL
    if (trimmed.startsWith('https://') ||
        (trimmed.startsWith('http://') &&
            !trimmed.contains('localhost') &&
            !trimmed.contains('127.0.0.1'))) {
      return trimmed;
    }

    // Relative backend path (e.g. /uploads/products/... or uploads/products/...)
    if (trimmed.startsWith('/uploads') || trimmed.startsWith('uploads/')) {
      final path = trimmed.startsWith('/') ? trimmed : '/$trimmed';
      return '$baseUrl$path';
    }

    if (trimmed.startsWith('/')) {
      return '$baseUrl$trimmed';
    }

    // If it points to localhost / 127.0.0.1 (e.g. stored in DB as http://localhost:8000/uploads/...)
    if (trimmed.contains('localhost:8000') ||
        trimmed.contains('127.0.0.1:8000')) {
      final uri = Uri.tryParse(trimmed);
      if (uri != null) {
        return '$baseUrl${uri.path}';
      }
    }

    // If it matches a known seeded asset basename
    for (final entry in _seededImageMap.entries) {
      if (trimmed.endsWith(entry.key.split('/').last)) {
        return entry.value;
      }
    }

    return trimmed;
  }

  // Name-based resolution for seeded products without an explicit URL
  static String _resolveByName(String name) {
    final lower = name.toLowerCase();
    if (lower.contains('nike') || lower.contains('air max')) {
      return _seededImageMap['assets/images/products/nike_airmax.png']!;
    }
    if (lower.contains('adidas') || lower.contains('ultraboost')) {
      return _seededImageMap['assets/images/products/adidas_ultraboost.png']!;
    }
    if (lower.contains('puma')) {
      return _seededImageMap['assets/images/products/puma_rsx.png']!;
    }
    if (lower.contains('new balance')) {
      return _seededImageMap['assets/images/products/new_balance.png']!;
    }
    if (lower.contains('sony') || lower.contains('wh-1000xm5')) {
      return _seededImageMap['assets/images/products/sony_headphones.png']!;
    }
    if (lower.contains('apple watch')) {
      return _seededImageMap['assets/images/products/apple_watch.png']!;
    }
    if (lower.contains('galaxy buds') || lower.contains('earbuds')) {
      return _seededImageMap['assets/images/products/galaxy_buds.png']!;
    }
    if (lower.contains('denim') || lower.contains('jacket')) {
      return _seededImageMap['assets/images/products/denim_jacket.png']!;
    }
    if (lower.contains('hoodie') || lower.contains('fleece')) {
      return _seededImageMap['assets/images/products/fleece_hoodie.png']!;
    }
    if (lower.contains('chino') || lower.contains('trouser')) {
      return _seededImageMap['assets/images/products/chinos.png']!;
    }
    if (lower.contains('wallet')) {
      return _seededImageMap['assets/images/products/leather_wallet.png']!;
    }
    if (lower.contains('oil') || lower.contains('skincare')) {
      return _seededImageMap['assets/images/products/face_oil.png']!;
    }
    return '';
  }

  // Network timeouts
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 15);

  // Authentication endpoints
  static const String login = '/api/v1/auth/login';
  static const String register = '/api/v1/auth/register';
  static const String logout = '/api/v1/auth/logout';
  static const String me = '/api/v1/auth/me';
  static const String refreshToken = '/api/v1/auth/refresh';
  static const String forgotPassword = '/api/v1/auth/forgot-password';
  static const String validateResetToken = '/api/v1/auth/reset-password/validate';
  static const String resetPassword = '/api/v1/auth/reset-password';

  // Public store settings & payment endpoints
  static const String publicSettings = '/api/v1/settings/public';
  static const String paymentsConfig = '/api/v1/payments/config';
  static const String paymentCardIntent = '/api/v1/payments/card/intent';
  static const String paymentCardConfirm = '/api/v1/payments/card/confirm';

  // Products endpoints
  static const String products = '/api/v1/products';
  static const String featuredProducts = '/api/v1/products/featured';
  static const String searchProducts = '/api/v1/products/search';
  static String productDetail(int id) => '/api/v1/products/$id';

  // Categories endpoints
  static const String categories = '/api/v1/categories';
  static String categoryProducts(int id) => '/api/v1/categories/$id/products';

  static const String addresses = '/api/v1/addresses';

  // Cart & Checkout endpoints
  static const String cart = '/api/v1/cart';
  static String cartItem(int id) => '/api/v1/cart/$id';
  static String cartProduct(int productId) => '/api/v1/cart/product/$productId';
  static const String checkout = '/api/v1/cart/checkout';

  // Coupons & Promo endpoints
  static const String couponsValidate = '/api/v1/coupons/validate';
  static const String couponsAvailable = '/api/v1/coupons/available';

  // Orders endpoints
  static const String orders = '/api/v1/orders';
  static String orderDetail(int id) => '/api/v1/orders/$id';
  static String orderTracking(int id) => '/api/v1/orders/$id/tracking';

  // Reviews endpoints
  static const String reviews = '/api/v1/reviews';
  static String productReviews(int productId) =>
      '/api/v1/reviews?product_id=$productId';
  static String submitReview(int productId) =>
      '/api/v1/reviews/product/$productId';
  static String reviewDetail(int id) => '/api/v1/reviews/$id';

  // Notifications endpoints
  static const String notifications = '/api/v1/notifications';
  static const String notificationsUnreadCount =
      '/api/v1/notifications/unread-count';
  static String notificationRead(int id) => '/api/v1/notifications/$id/read';
  static const String notificationsReadAll = '/api/v1/notifications/read-all';
  static String notificationDelete(int id) => '/api/v1/notifications/$id';
}
