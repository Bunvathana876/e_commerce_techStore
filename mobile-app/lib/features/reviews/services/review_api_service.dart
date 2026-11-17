import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/review_model.dart';

/// Service connecting to the backend reviews API endpoints
class ReviewApiService {
  final ApiClient _client;

  ReviewApiService({ApiClient? client})
    : _client = client ?? ApiClient.instance;

  /// Fetch approved reviews for a specific product
  Future<List<ReviewModel>> getProductReviews(int productId) async {
    try {
      final response = await _client.get<List<ReviewModel>>(
        ApiEndpoints.reviews,
        queryParameters: {'product_id': productId, 'status': 'approved'},
        parser: (data) => _parseReviewList(data),
      );

      return response.data ?? [];
    } catch (e) {
      // In case of network errors or fallback, return empty list gracefully
      return [];
    }
  }

  /// Submit a new review for a product
  Future<ReviewModel> submitReview({
    required int productId,
    required int rating,
    required String comment,
    int? orderId,
  }) async {
    final body = <String, dynamic>{'rating': rating, 'comment': comment.trim()};

    if (orderId != null && orderId > 0) {
      body['order_id'] = orderId;
    }

    final response = await _client.post<ReviewModel>(
      ApiEndpoints.submitReview(productId),
      body: body,
      parser: (data) => ReviewModel.fromJson(data as Map<String, dynamic>),
    );

    if (response.data == null) {
      throw Exception(
        response.message.isNotEmpty
            ? response.message
            : 'Failed to submit review',
      );
    }

    return response.data!;
  }

  /// Helper to parse review list payload from backend
  List<ReviewModel> _parseReviewList(dynamic data) {
    if (data is List) {
      return data
          .map((item) => ReviewModel.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }
}
