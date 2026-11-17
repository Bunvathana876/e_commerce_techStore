import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:e_commerc_mobile_app/core/constants/api_endpoints.dart';
import 'package:e_commerc_mobile_app/core/network/api_client.dart';
import 'package:e_commerc_mobile_app/core/network/api_exceptions.dart';
import 'package:e_commerc_mobile_app/core/network/api_response.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';
import 'package:e_commerc_mobile_app/features/products/services/product_api_service.dart';

void main() {
  group('ApiEndpoints Tests', () {
    tearDown(() {
      ApiEndpoints.resetBaseUrl();
    });

    test('Default baseUrl is available and non-empty', () {
      expect(ApiEndpoints.baseUrl, isNotEmpty);
      expect(ApiEndpoints.baseUrl.startsWith('http'), isTrue);
    });

    test('Custom baseUrl overrides default', () {
      ApiEndpoints.setBaseUrl('https://api.my-ecommerce.com');
      expect(ApiEndpoints.baseUrl, 'https://api.my-ecommerce.com');

      // Removes trailing slash
      ApiEndpoints.setBaseUrl('https://api.my-ecommerce.com/');
      expect(ApiEndpoints.baseUrl, 'https://api.my-ecommerce.com');

      ApiEndpoints.resetBaseUrl();
      expect(ApiEndpoints.baseUrl, isNot('https://api.my-ecommerce.com'));
    });

    test(
      'Release API configuration rejects missing, insecure and malformed origins',
      () {
        for (final url in [
          '',
          'http://api.example.com',
          'https://localhost',
          'https://127.0.0.1',
          'https://[::1]',
          'https://10.0.2.2',
          'https://api.example.com/api',
          'https://user:pass@api.example.com',
          'https://api.example.com?token=x',
          'https://api.example.com#fragment',
        ]) {
          expect(
            () => ApiEndpoints.validateBaseUrl(url, requireHttps: true),
            throwsArgumentError,
            reason: url,
          );
        }
        expect(
          ApiEndpoints.validateBaseUrl(
            'https://api.example.com/',
            requireHttps: true,
          ),
          'https://api.example.com',
        );
        expect(
          ApiEndpoints.validateBaseUrl(
            'http://localhost:8000',
            requireHttps: false,
          ),
          'http://localhost:8000',
        );
      },
    );

    test('Dynamic route builders format URLs properly', () {
      expect(ApiEndpoints.productDetail(42), '/api/v1/products/42');
      expect(ApiEndpoints.categoryProducts(5), '/api/v1/categories/5/products');
      expect(ApiEndpoints.cartItem(12), '/api/v1/cart/12');
      expect(ApiEndpoints.cartProduct(12), '/api/v1/cart/product/12');
      expect(ApiEndpoints.orderDetail(99), '/api/v1/orders/99');
    });
  });

  group('ApiException Tests', () {
    test('Extracts simple detail from FastAPI JSON error', () {
      const jsonStr = '{"detail": "Incorrect password"}';
      final msg = ApiException.extractErrorMessage(jsonStr);
      expect(msg, 'Incorrect password');
    });

    test('Extracts validation array error from FastAPI', () {
      const jsonStr =
          '{"detail": [{"loc": ["body", "email"], "msg": "value is not a valid email"}]}';
      final msg = ApiException.extractErrorMessage(jsonStr);
      expect(msg, 'value is not a valid email');
    });

    test('Falls back when body is not JSON', () {
      const plainStr = '502 Bad Gateway';
      final msg = ApiException.extractErrorMessage(plainStr);
      expect(msg, 'An unexpected error occurred');
    });

    test('Maps HTTP status codes to typed exceptions', () {
      expect(
        ApiException.fromStatusCode(400, '{"detail": "Bad"}'),
        isA<BadRequestException>(),
      );
      expect(
        ApiException.fromStatusCode(401, '{"detail": "Unauthorized"}'),
        isA<UnauthorizedException>(),
      );
      expect(
        ApiException.fromStatusCode(403, '{"detail": "Forbidden"}'),
        isA<ForbiddenException>(),
      );
      expect(
        ApiException.fromStatusCode(404, '{"detail": "Not found"}'),
        isA<NotFoundException>(),
      );
      expect(
        ApiException.fromStatusCode(409, '{"detail": "Conflict"}'),
        isA<ConflictException>(),
      );
      expect(
        ApiException.fromStatusCode(500, '{"detail": "Server error"}'),
        isA<ServerException>(),
      );
    });
  });

  group('ApiResponse Tests', () {
    test('ApiResponse.success stores payload', () {
      final response = ApiResponse<String>.success('hello');
      expect(response.success, isTrue);
      expect(response.data, 'hello');
      expect(response.statusCode, 200);
    });

    test('ApiResponse.failure stores error details', () {
      final response = ApiResponse<int>.failure('Failed', statusCode: 400);
      expect(response.success, isFalse);
      expect(response.message, 'Failed');
      expect(response.statusCode, 400);
    });
  });

  group('ApiClient Tests', () {
    test('Successful GET parses data and injects headers', () async {
      final mockClient = MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.headers['Accept'], 'application/json');
        expect(request.headers['Authorization'], 'Bearer test_token');

        final data = [
          {
            'id': 1,
            'name': 'Wireless Headphones',
            'description': 'Noise cancelling',
            'price': 99.99,
            'rating': 4.8,
            'review_count': 120,
            'category_id': 1,
            'image_url': 'https://example.com/headphones.png',
          },
        ];

        return http.Response(jsonEncode(data), 200);
      });

      final apiClient = ApiClient(client: mockClient);
      apiClient.setAuthToken('test_token');

      final response = await apiClient.get<List<ProductModel>>(
        '/test-products',
        parser: (data) => (data as List)
            .map((item) => ProductModel.fromJson(item as Map<String, dynamic>))
            .toList(),
      );

      expect(response.success, isTrue);
      expect(response.data?.length, 1);
      expect(response.data?.first.name, 'Wireless Headphones');
      expect(response.data?.first.price, 99.99);
    });

    test('Non-200 response throws typed ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode({'detail': 'Token expired'}), 401);
      });

      final apiClient = ApiClient(client: mockClient);

      expect(
        () => apiClient.get<dynamic>('/protected'),
        throwsA(isA<UnauthorizedException>()),
      );
    });

    test('ProductApiService integrates seamlessly with ApiClient', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, endsWith('/api/v1/products'));
        expect(request.url.queryParameters['category_id'], '2');

        final products = [
          {
            'id': 10,
            'name': 'Smart Watch',
            'description': 'Fitness tracking',
            'price': 149.50,
            'rating': 4.5,
            'review_count': 85,
            'category_id': 2,
            'image_url': '',
          },
        ];

        return http.Response(jsonEncode(products), 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final productService = ProductApiService(client: apiClient);

      final result = await productService.getProducts(categoryId: 2);
      expect(result.length, 1);
      expect(result.first.name, 'Smart Watch');
      expect(result.first.price, 149.50);
    });
  });

  group('normalizeImageUrl Tests', () {
    test('Resolves seeded database asset paths to Unsplash URLs', () {
      final nike = ApiEndpoints.normalizeImageUrl(
        'assets/images/products/nike_airmax.png',
      );
      expect(nike, startsWith('https://images.unsplash.com/'));

      final sony = ApiEndpoints.normalizeImageUrl(
        'assets/images/products/sony_headphones.png',
      );
      expect(sony, startsWith('https://images.unsplash.com/'));

      final categoryShoe = ApiEndpoints.normalizeImageUrl(
        'assets/images/products/shoe.png',
      );
      expect(categoryShoe, startsWith('https://images.unsplash.com/'));
    });

    test('Prepends baseUrl to relative upload paths', () {
      final upload = ApiEndpoints.normalizeImageUrl(
        '/uploads/products/item.png',
      );
      expect(upload, '${ApiEndpoints.baseUrl}/uploads/products/item.png');

      final uploadNoSlash = ApiEndpoints.normalizeImageUrl(
        'uploads/products/item2.png',
      );
      expect(
        uploadNoSlash,
        '${ApiEndpoints.baseUrl}/uploads/products/item2.png',
      );
    });

    test('Resolves dead trycloudflare tunnel to working fallback', () {
      final resolved = ApiEndpoints.normalizeImageUrl(
        'https://nick-howto-bowl-cute.trycloudflare.com/images/5bb19765af44.jpg',
      );
      expect(resolved, startsWith('https://images.unsplash.com/'));
    });

    test('Resolves by product name when URL is empty', () {
      final resolved = ApiEndpoints.normalizeImageUrl(
        '',
        fallbackName: 'Nike Air Max 270',
      );
      expect(resolved, startsWith('https://images.unsplash.com/'));
    });
  });
}
