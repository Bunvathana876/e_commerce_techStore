import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../models/order_model.dart';

/// REST API service for Orders, connecting to FastAPI backend
class OrderApiService {
  final ApiClient _client;

  OrderApiService({ApiClient? client}) : _client = client ?? ApiClient.instance;

  ApiClient get client => _client;

  /// Fetch all orders placed by the current authenticated user
  Future<List<OrderModel>> getOrders() async {
    final response = await _client.get<List<OrderModel>>(
      ApiEndpoints.orders,
      parser: (data) => _parseOrderList(data),
    );

    return response.data ?? [];
  }

  /// Fetch a single order's complete details by ID
  Future<OrderModel?> getOrderById(int orderId) async {
    final response = await _client.get<OrderModel?>(
      ApiEndpoints.orderDetail(orderId),
      parser: (data) {
        if (data is Map<String, dynamic>) {
          final orderData = data['data'] ?? data;
          if (orderData is Map<String, dynamic>) {
            return OrderModel.fromJson(orderData);
          }
        }
        return null;
      },
    );

    return response.data;
  }

  /// Place a new order via the backend API.
  /// Throws [ApiException] if the server does not return a confirmed order ID.
  Future<OrderModel> createOrder({
    required String shippingAddress,
    required String paymentMethod,
    int? shippingAddressId,
    String? phone,
    String? fullName,
    String? couponCode,
    String? idempotencyKey,
    List<Map<String, dynamic>>? items,
  }) async {
    final body = <String, dynamic>{
      'shipping_address': shippingAddress,
      'shipping_address_id': ?shippingAddressId,
      'payment_method': paymentMethod,
      'phone': ?phone,
      'full_name': ?fullName,
      'coupon_code': ?couponCode,
      'idempotency_key': ?idempotencyKey,
      'items': ?items,
    };
    final headers = <String, String>{'Idempotency-Key': ?idempotencyKey};

    final response = await _client.post<OrderModel?>(
      ApiEndpoints.orders,
      body: body,
      headers: headers.isNotEmpty ? headers : null,
      parser: (data) {
        if (data is Map<String, dynamic>) {
          final orderData = data['data'] ?? data;
          if (orderData is Map<String, dynamic>) {
            return OrderModel.fromJson(orderData);
          }
        }
        return null;
      },
    );

    final created = response.data;
    if (!response.success || created == null || created.id <= 0) {
      throw ApiException(
        response.message.isNotEmpty
            ? response.message
            : 'Unable to confirm order with server.',
        statusCode: response.statusCode,
      );
    }

    return created;
  }

  /// Parses order list from backend enveloped or raw list format
  List<OrderModel> _parseOrderList(dynamic data) {
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((item) => OrderModel.fromJson(item))
          .toList();
    }
    if (data is Map<String, dynamic>) {
      final list = data['orders'] ?? data['data'] ?? data['items'];
      if (list is List) {
        return list
            .whereType<Map<String, dynamic>>()
            .map((item) => OrderModel.fromJson(item))
            .toList();
      }
    }
    return [];
  }
}
