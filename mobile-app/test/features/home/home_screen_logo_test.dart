import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:e_commerc_mobile_app/features/auth/providers/auth_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/categories/providers/category_provider.dart';
import 'package:e_commerc_mobile_app/features/home/screens/home_screen.dart';
import 'package:e_commerc_mobile_app/features/notifications/providers/notification_provider.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';
import 'package:e_commerc_mobile_app/shared/widgets/app_logo.dart';
import 'package:e_commerc_mobile_app/shared/widgets/app_search_bar.dart';

void main() {
  testWidgets(
    'HomeScreen displays redesigned minimal top navigation and search header',
    (WidgetTester tester) async {
      final productProvider = ProductProvider();
      final categoryProvider = CategoryProvider();
      final cartProvider = CartProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
          ],
          child: const MaterialApp(home: HomeScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Verify top navigation row: Brand logo, Store name, Notification button, and Profile avatar (NO hamburger menu)
      expect(find.byType(AppLogo), findsOneWidget);
      expect(find.text('Blue Panda'), findsOneWidget);
      expect(find.byIcon(Icons.menu_rounded), findsNothing);
      expect(find.byIcon(Icons.notifications_none_rounded), findsOneWidget);
      expect(find.byIcon(Icons.person_outline_rounded), findsOneWidget);

      // Verify search row: Pill search field with placeholder and search icon
      expect(find.text("What's on your list?"), findsOneWidget);
      expect(find.byIcon(Icons.search_rounded), findsOneWidget);

      // Verify separate circular filter button with white tune icon
      expect(find.byIcon(Icons.tune_rounded), findsOneWidget);

      // Verify See all is displayed
      expect(find.text('See all'), findsOneWidget);
    },
  );

  testWidgets(
    'HomeScreen omits hamburger menu button and keeps top bar minimal',
    (WidgetTester tester) async {
      final productProvider = ProductProvider();
      final categoryProvider = CategoryProvider();
      final cartProvider = CartProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
          ],
          child: const MaterialApp(home: HomeScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Ensure no hamburger or drawer menu icon is rendered
      expect(find.byIcon(Icons.menu_rounded), findsNothing);
      expect(find.byIcon(Icons.menu), findsNothing);
    },
  );

  testWidgets(
    'Tapping profile avatar triggers onProfileTap callback when supplied',
    (WidgetTester tester) async {
      var profileTriggered = false;
      final productProvider = ProductProvider();
      final categoryProvider = CategoryProvider();
      final cartProvider = CartProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
          ],
          child: MaterialApp(
            home: HomeScreen(
              onProfileTap: () {
                profileTriggered = true;
              },
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.person_outline_rounded));
      await tester.pumpAndSettle();

      expect(profileTriggered, isTrue);
    },
  );

  testWidgets(
    'Tapping See all triggers onSeeAllCategories callback when supplied',
    (WidgetTester tester) async {
      var callbackTriggered = false;
      final productProvider = ProductProvider();
      final categoryProvider = CategoryProvider();
      final cartProvider = CartProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
          ],
          child: MaterialApp(
            home: HomeScreen(
              onSeeAllCategories: () {
                callbackTriggered = true;
              },
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.text('See all'));
      await tester.pumpAndSettle();

      expect(callbackTriggered, isTrue);
    },
  );

  testWidgets(
    'Tapping See all navigates to CategoriesScreen when no callback is supplied',
    (WidgetTester tester) async {
      final productProvider = ProductProvider();
      final categoryProvider = CategoryProvider();
      final cartProvider = CartProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
          ],
          child: const MaterialApp(home: HomeScreen()),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.text('See all'));
      await tester.pumpAndSettle();

      // Verify that CategoriesScreen is pushed
      expect(find.text('Search collections & departments...'), findsOneWidget);
    },
  );

  testWidgets(
    'HomeScreen renders authenticated user initial and unread notification badge',
    (WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({
        'auth_token': 'fake_token',
        'auth_user': jsonEncode({
          'id': 1,
          'email': 'jane@example.com',
          'full_name': 'Jane Doe',
          'role': 'customer',
        }),
      });
      final prefs = await SharedPreferences.getInstance();
      final authProvider = AuthProvider(initialPrefs: prefs);
      final notificationProvider = NotificationProvider();
      final productProvider = ProductProvider();
      final categoryProvider = CategoryProvider();
      final cartProvider = CartProvider();

      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: productProvider),
            ChangeNotifierProvider.value(value: categoryProvider),
            ChangeNotifierProvider.value(value: cartProvider),
            ChangeNotifierProvider.value(value: authProvider),
            ChangeNotifierProvider.value(value: notificationProvider),
          ],
          child: const MaterialApp(home: HomeScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Verify user initial 'J' is rendered in profile avatar
      expect(find.text('J'), findsOneWidget);

      // Verify notification button has an unread indicator child
      final notifIconFinder = find.byIcon(Icons.notifications_none_rounded);
      expect(notifIconFinder, findsOneWidget);
    },
  );

  testWidgets('HomeScreen header search and filter interactions work as expected', (
    WidgetTester tester,
  ) async {
    final productProvider = ProductProvider();
    final categoryProvider = CategoryProvider();
    final cartProvider = CartProvider();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: productProvider),
          ChangeNotifierProvider.value(value: categoryProvider),
          ChangeNotifierProvider.value(value: cartProvider),
        ],
        child: const MaterialApp(home: HomeScreen()),
      ),
    );

    await tester.pumpAndSettle();

    // Verify search bar has pill-shaped border radius (28px)
    final searchBarFinder = find.byType(AppSearchBar);
    expect(searchBarFinder, findsOneWidget);
    final searchBar = tester.widget<AppSearchBar>(searchBarFinder);
    expect(searchBar.borderRadius, BorderRadius.circular(28));

    // Verify search input interaction
    await tester.enterText(
      find.widgetWithText(TextField, "What's on your list?"),
      'shoes',
    );
    await tester.pumpAndSettle();

    expect(productProvider.searchQuery, equals('shoes'));
    expect(find.byKey(const Key('search_clear_button')), findsOneWidget);

    // Verify clear button
    await tester.tap(find.byKey(const Key('search_clear_button')));
    await tester.pumpAndSettle();

    expect(productProvider.searchQuery, isEmpty);
    expect(find.byKey(const Key('search_clear_button')), findsNothing);

    // Tap separate circular filter button
    await tester.tap(find.byIcon(Icons.tune_rounded));
    await tester.pumpAndSettle();

    // Verify Sort & Filter bottom sheet opened
    expect(find.text('Sort Products'), findsOneWidget);
  });
}

