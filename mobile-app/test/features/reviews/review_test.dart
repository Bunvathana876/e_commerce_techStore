import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';
import 'package:e_commerc_mobile_app/features/products/screens/product_detail_screen.dart';
import 'package:e_commerc_mobile_app/features/reviews/models/review_model.dart';
import 'package:e_commerc_mobile_app/features/reviews/providers/review_provider.dart';
import 'package:e_commerc_mobile_app/features/reviews/widgets/review_card.dart';
import 'package:e_commerc_mobile_app/features/reviews/widgets/write_review_bottom_sheet.dart';

void main() {
  const testProduct = ProductModel(
    id: 13,
    name: 'Nike Air Max 270',
    description: 'Iconic running sneakers with max air cushion.',
    price: 149.99,
    rating: 4.8,
    reviewCount: 42,
    categoryId: 3,
    imageUrl: '',
    isFavorite: false,
  );

  final testReview1 = ReviewModel(
    id: 1,
    productId: 13,
    userId: 9,
    rating: 5,
    comment: 'Exceptional comfort and looks stunning!',
    status: 'approved',
    createdAt: DateTime.now().subtract(const Duration(days: 2)),
    userName: 'Lee Min',
    userEmail: 'lee@example.com',
  );

  final testReview2 = ReviewModel(
    id: 2,
    productId: 13,
    userId: 10,
    rating: 4,
    comment: 'Good fit, true to size.',
    status: 'approved',
    adminReply: 'Thank you for your feedback! Enjoy your run.',
    adminRepliedAt: DateTime.now().subtract(const Duration(days: 1)),
    createdAt: DateTime.now().subtract(const Duration(days: 3)),
    userName: 'Sarah Jenkins',
    userEmail: 'sarah@example.com',
  );

  group('ReviewModel Unit Tests', () {
    test('parses from standard backend JSON correctly', () {
      final json = {
        'id': 101,
        'product_id': 13,
        'user_id': 5,
        'rating': 5,
        'comment': 'Love it!',
        'status': 'approved',
        'created_at': '2026-09-27T06:54:52.000',
        'user': {
          'id': 5,
          'name': 'John Doe',
          'email': 'john@example.com',
          'avatar': null,
        },
      };

      final review = ReviewModel.fromJson(json);

      expect(review.id, 101);
      expect(review.productId, 13);
      expect(review.userName, 'John Doe');
      expect(review.userInitials, 'JD');
      expect(review.rating, 5);
      expect(review.comment, 'Love it!');
      expect(review.isApproved, isTrue);
    });

    test('generates initials correctly for single and multi-word names', () {
      final r1 = ReviewModel(
        id: 1,
        productId: 1,
        userId: 1,
        rating: 5,
        comment: '',
        status: 'approved',
        createdAt: DateTime.now(),
        userName: 'Alex',
      );
      expect(r1.userInitials, 'A');

      final r2 = ReviewModel(
        id: 2,
        productId: 1,
        userId: 1,
        rating: 5,
        comment: '',
        status: 'approved',
        createdAt: DateTime.now(),
        userName: 'Alex Johnson',
      );
      expect(r2.userInitials, 'AJ');
    });
  });

  group('ReviewCard Widget Tests', () {
    testWidgets('renders user name, stars, date, comment, and verified badge', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReviewCard(review: testReview1, isDark: false),
          ),
        ),
      );

      expect(find.text('Lee Min'), findsOneWidget);
      expect(find.text('Verified'), findsOneWidget);
      expect(find.text('Exceptional comfort and looks stunning!'), findsOneWidget);
      expect(find.byIcon(Icons.star_rounded), findsNWidgets(5));
    });

    testWidgets('renders store admin response bubble when admin reply is present', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReviewCard(review: testReview2, isDark: false),
          ),
        ),
      );

      expect(find.text('Sarah Jenkins'), findsOneWidget);
      expect(find.text('Store Response'), findsOneWidget);
      expect(
        find.text('Thank you for your feedback! Enjoy your run.'),
        findsOneWidget,
      );
    });
  });

  group('WriteReviewBottomSheet Widget Tests', () {
    testWidgets('renders star selector, comment text area, and submit button', (
      WidgetTester tester,
    ) async {
      final reviewProvider = ReviewProvider();
      final authProvider = AuthProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ReviewProvider>.value(value: reviewProvider),
            ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: WriteReviewBottomSheet(
                productId: 13,
                productName: 'Nike Air Max 270',
              ),
            ),
          ),
        ),
      );

      expect(find.text('Write a Review'), findsOneWidget);
      expect(find.text('Nike Air Max 270'), findsOneWidget);
      expect(find.text('Excellent!'), findsOneWidget); // Default 5 stars
      expect(find.byType(TextField), findsWidgets);
      expect(find.text('Submit Review'), findsOneWidget);

      // Tap 4th star to set rating to 4
      final stars = find.byIcon(Icons.star_rounded);
      expect(stars, findsNWidgets(5));
      await tester.tap(stars.at(3));
      await tester.pump();
      expect(find.text('Good'), findsOneWidget);
    });
  });

  group('ProductDetailScreen Reviews Integration Tests', () {
    testWidgets('renders Customer Ratings section with Write Review button', (
      WidgetTester tester,
    ) async {
      final productProvider = ProductProvider();
      final cartProvider = CartProvider();
      final reviewProvider = ReviewProvider();
      final authProvider = AuthProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ProductProvider>.value(value: productProvider),
            ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
            ChangeNotifierProvider<ReviewProvider>.value(value: reviewProvider),
            ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const ProductDetailScreen(product: testProduct),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Ensure Customer Ratings and Verified ratings are displayed
      expect(find.text('Customer Ratings'), findsWidgets);
      expect(find.text('42 Verified Ratings'), findsOneWidget);
      expect(find.text('Write Review'), findsOneWidget);

      // Tap Write Review button to open bottom sheet
      await tester.ensureVisible(find.byKey(const Key('write_review_button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('write_review_button')));
      await tester.pumpAndSettle();

      // Bottom sheet is now presented
      expect(find.text('Write a Review'), findsOneWidget);
      expect(find.text('Submit Review'), findsOneWidget);
    });

    testWidgets('Interactive Rating Breakdown bars render and filter reviews by star on tap', (
      WidgetTester tester,
    ) async {
      final productProvider = ProductProvider();
      final cartProvider = CartProvider();
      final reviewProvider = ReviewProvider();
      final authProvider = AuthProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider<ProductProvider>.value(value: productProvider),
            ChangeNotifierProvider<CartProvider>.value(value: cartProvider),
            ChangeNotifierProvider<ReviewProvider>.value(value: reviewProvider),
            ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const ProductDetailScreen(product: testProduct),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Scroll down to reveal the ratings breakdown
      await tester.ensureVisible(find.byKey(const Key('rating_bar_5')));
      await tester.pumpAndSettle();

      // Verify all 5 rating bars exist
      expect(find.byKey(const Key('rating_bar_5')), findsOneWidget);
      expect(find.byKey(const Key('rating_bar_4')), findsOneWidget);
      expect(find.byKey(const Key('rating_bar_3')), findsOneWidget);
      expect(find.byKey(const Key('rating_bar_2')), findsOneWidget);
      expect(find.byKey(const Key('rating_bar_1')), findsOneWidget);

      // Tap 5-star rating bar to filter to 5-star reviews
      await tester.tap(find.byKey(const Key('rating_bar_5')));
      await tester.pumpAndSettle();

      // Banner should display showing 5 star reviews
      expect(find.textContaining('Showing 5 ★ Reviews'), findsOneWidget);
      expect(find.byKey(const Key('clear_star_filter_button')), findsOneWidget);

      // Tap clear filter button
      await tester.tap(find.byKey(const Key('clear_star_filter_button')));
      await tester.pumpAndSettle();

      // Banner is removed
      expect(find.byKey(const Key('clear_star_filter_button')), findsNothing);

      // Tap 1-star bar (which has 0 reviews in sample)
      await tester.tap(find.byKey(const Key('rating_bar_1')));
      await tester.pumpAndSettle();

      // Empty state for 1-star reviews should appear
      expect(find.text('No 1-star reviews yet'), findsOneWidget);
      expect(find.text('Show All Reviews'), findsOneWidget);

      // Tap Show All Reviews
      await tester.tap(find.text('Show All Reviews'));
      await tester.pumpAndSettle();

      expect(find.text('No 1-star reviews yet'), findsNothing);
    });
  });
}

