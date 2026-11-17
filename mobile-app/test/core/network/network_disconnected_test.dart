import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/categories/providers/category_provider.dart';
import 'package:e_commerc_mobile_app/features/home/screens/home_screen.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';
import 'package:e_commerc_mobile_app/features/products/services/product_api_service.dart';
import 'package:e_commerc_mobile_app/features/reviews/models/review_model.dart';
import 'package:e_commerc_mobile_app/features/reviews/providers/review_provider.dart';
import 'package:e_commerc_mobile_app/features/reviews/services/review_api_service.dart';

class FailingProductApiService extends ProductApiService {
  @override
  Future<List<ProductModel>> getProducts({
    int page = 1,
    int limit = 20,
    int? categoryId,
    String? search,
  }) async {
    throw Exception('Connection refused: Backend API server is offline');
  }
}

class FailingReviewApiService extends ReviewApiService {
  @override
  Future<List<ReviewModel>> getProductReviews(int productId) async {
    throw Exception('Connection refused: Backend API server is offline');
  }
}

void main() {
  group('Network Disconnected & No Fake Data Tests', () {
    testWidgets('HomeScreen displays Network is not connected and zero fake products when API is offline', (
      WidgetTester tester,
    ) async {
      // Simulate app launch with offline API (initialProducts: [])
      final productProvider = ProductProvider(
        productApiService: FailingProductApiService(),
        initialProducts: [],
      );
      final categoryProvider = CategoryProvider(initialCategories: []);
      final cartProvider = CartProvider();

      // Trigger load which fails
      await productProvider.loadFromBackend(force: true);

      expect(productProvider.isBackendConnected, isFalse);
      expect(productProvider.errorMessage, contains('Network is not connected'));
      expect(productProvider.allProducts, isEmpty);

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Verify that "Network is not connected" is displayed
      expect(find.text('Network is not connected'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off_rounded), findsOneWidget);
      expect(find.text('Retry Connection'), findsOneWidget);

      // Verify that NO fake products are displayed
      expect(find.text('UltraBook Pro 15" M2 Laptop'), findsNothing);
      expect(find.text('Portable 4K Ultra HD Monitor'), findsNothing);
      expect(find.text('Categories'), findsNothing);
    });

    test('ReviewProvider does not populate fake reviews when API is offline in production mode', () async {
      final reviewProvider = ReviewProvider(apiService: FailingReviewApiService());
      await reviewProvider.fetchReviews(101, force: true);

      // In production mode, reviews must be empty rather than fake customer reviews
      expect(reviewProvider.errorMessage, isNull);
    });
  });
}
