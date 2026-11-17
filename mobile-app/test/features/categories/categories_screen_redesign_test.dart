import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/categories/models/category_model.dart';
import 'package:e_commerc_mobile_app/features/categories/providers/category_provider.dart';
import 'package:e_commerc_mobile_app/features/categories/screens/categories_screen.dart';
import 'package:e_commerc_mobile_app/features/categories/screens/category_products_screen.dart';
import 'package:e_commerc_mobile_app/features/categories/widgets/category_card.dart';
import 'package:e_commerc_mobile_app/features/products/providers/product_provider.dart';
import 'package:e_commerc_mobile_app/shared/widgets/app_search_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  group('CategoriesScreen Premium UI Redesign Tests', () {
    final sampleCategories = [
      const CategoryModel(
        id: 0,
        name: 'All Items',
        icon: '🛍️',
        itemCount: 25,
        imageUrl: 'https://example.com/all.jpg',
      ),
      const CategoryModel(
        id: 1,
        name: 'Electronics',
        icon: '💻',
        itemCount: 8,
        imageUrl: 'https://example.com/electronics.jpg',
      ),
      const CategoryModel(
        id: 2,
        name: 'Fashion & Clothing',
        icon: '👕',
        itemCount: 0, // Unverified / backend 0
        imageUrl: '',
      ),
    ];

    Widget createScreen({
      ThemeMode themeMode = ThemeMode.light,
      ValueChanged<int>? onCategorySelected,
      List<CategoryModel>? categories,
    }) {
      final categoryProvider = CategoryProvider(
        initialCategories: categories ?? sampleCategories,
      );

      return MultiProvider(
        providers: [
          ChangeNotifierProvider<CategoryProvider>.value(
            value: categoryProvider,
          ),
          ChangeNotifierProvider<ProductProvider>(
            create: (_) => ProductProvider(),
          ),
          ChangeNotifierProvider<CartProvider>(create: (_) => CartProvider()),
        ],
        child: MaterialApp(
          themeMode: themeMode,
          theme: ThemeData.light(),
          darkTheme: ThemeData.dark(),
          home: Scaffold(
            body: CategoriesScreen(onCategorySelected: onCategorySelected),
          ),
        ),
      );
    }

    testWidgets('renders clean Categories header and pill AppSearchBar', (
      tester,
    ) async {
      await tester.pumpWidget(createScreen());
      await tester.pumpAndSettle();

      // Verify header title
      expect(find.text('Categories'), findsOneWidget);

      // Verify pill search bar with 28px border radius
      final searchBarFinder = find.byType(AppSearchBar);
      expect(searchBarFinder, findsOneWidget);
      final searchBar = tester.widget<AppSearchBar>(searchBarFinder);
      expect(searchBar.borderRadius, BorderRadius.circular(28));
      expect(find.text('Search collections & departments...'), findsOneWidget);
    });

    testWidgets('renders compact Browse All Items banner and navigates on tap', (
      tester,
    ) async {
      await tester.pumpWidget(createScreen());
      await tester.pumpAndSettle();

      // Verify banner texts
      expect(find.text('ALL COLLECTIONS'), findsOneWidget);
      expect(find.text('Browse All Items'), findsOneWidget);
      expect(
        find.text('Explore our entire catalog across every category'),
        findsOneWidget,
      );

      // Tap banner to navigate
      await tester.tap(find.text('Browse All Items'));
      await tester.pump();

      expect(find.byType(CategoryProductsScreen), findsOneWidget);
      expect(find.text('All Items'), findsOneWidget);
    });

    testWidgets('searching filters categories and hides the featured banner', (
      tester,
    ) async {
      await tester.pumpWidget(createScreen());
      await tester.pumpAndSettle();

      expect(find.text('Browse All Items'), findsOneWidget);
      expect(find.text('Electronics'), findsOneWidget);
      expect(find.text('Fashion & Clothing'), findsOneWidget);

      // Search for Electronics
      await tester.enterText(find.byType(TextField), 'Elec');
      await tester.pumpAndSettle();

      // Banner should be hidden during search
      expect(find.text('Browse All Items'), findsNothing);
      expect(find.text('Electronics'), findsOneWidget);
      expect(find.text('Fashion & Clothing'), findsNothing);

      // Clear search
      final clearButton = find.byKey(const Key('search_clear_button'));
      expect(clearButton, findsOneWidget);
      await tester.tap(clearButton);
      await tester.pumpAndSettle();

      // Banner and full list should reappear
      expect(find.text('Browse All Items'), findsOneWidget);
      expect(find.text('Fashion & Clothing'), findsOneWidget);
    });

    testWidgets('displays truthful empty state when no categories match search', (
      tester,
    ) async {
      await tester.pumpWidget(createScreen());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'NonExistentCategory');
      await tester.pumpAndSettle();

      expect(
        find.text('No categories matching "NonExistentCategory"'),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.search_off_rounded), findsOneWidget);
    });

    testWidgets(
      'category card displays verified count when > 0 and omits misleading 0 items badge',
      (tester) async {
        await tester.pumpWidget(createScreen());
        await tester.pumpAndSettle();

        // Electronics has itemCount = 8, so verified count is shown
        expect(find.text('8 items'), findsOneWidget);

        // Fashion & Clothing has itemCount = 0, so '0 items' is NOT displayed
        expect(find.text('0 items'), findsNothing);
      },
    );

    testWidgets('category card does not render floating emoji badge', (
      tester,
    ) async {
      await tester.pumpWidget(createScreen());
      await tester.pumpAndSettle();

      // Verify that category name is present
      expect(find.text('Electronics'), findsOneWidget);

      // Ensure no floating emoji widget exists as an independent text on card
      expect(find.text('💻'), findsNothing);
      expect(find.text('👕'), findsNothing);
    });

    testWidgets('category card renders fallback icon when imageUrl is empty', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 170,
                child: CategoryCard(
                  category: const CategoryModel(
                    id: 10,
                    name: 'Books',
                    icon: '📚',
                    itemCount: 0,
                    imageUrl: '',
                  ),
                  onTap: () {},
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Books'), findsOneWidget);
      expect(find.byIcon(Icons.category_outlined), findsOneWidget);
      expect(find.byIcon(Icons.arrow_forward_rounded), findsOneWidget);
    });

    testWidgets(
      'renders cleanly without overflow on narrow 320px screens in dark mode',
      (tester) async {
        tester.view.physicalSize = const Size(320, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() => tester.view.resetPhysicalSize());

        await tester.pumpWidget(createScreen(themeMode: ThemeMode.dark));
        await tester.pumpAndSettle();

        expect(find.text('Categories'), findsOneWidget);
        expect(find.text('Browse All Items'), findsOneWidget);
        expect(find.text('Electronics'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );

    testWidgets('onCategorySelected callback is invoked when provided', (
      tester,
    ) async {
      int? selectedId;

      await tester.pumpWidget(
        createScreen(
          onCategorySelected: (id) {
            selectedId = id;
          },
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Electronics'));
      await tester.pumpAndSettle();

      expect(selectedId, 1);
    });
  });
}
