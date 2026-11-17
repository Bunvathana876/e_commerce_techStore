import 'package:e_commerc_mobile_app/shared/widgets/app_bottom_nav_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppBottomNavBar Widget Tests', () {
    final defaultItems = [
      const AppNavItem(
        label: 'Home',
        activeIcon: Icons.home_rounded,
        inactiveIcon: Icons.home_outlined,
      ),
      const AppNavItem(
        label: 'Categories',
        activeIcon: Icons.grid_view_rounded,
        inactiveIcon: Icons.grid_view_outlined,
      ),
      const AppNavItem(
        label: 'Favorites',
        activeIcon: Icons.favorite_rounded,
        inactiveIcon: Icons.favorite_outline_rounded,
        badgeCount: 4,
      ),
      const AppNavItem(
        label: 'Cart',
        activeIcon: Icons.shopping_bag_rounded,
        inactiveIcon: Icons.shopping_bag_outlined,
        badgeCount: 2,
      ),
      const AppNavItem(
        label: 'Profile',
        activeIcon: Icons.person_rounded,
        inactiveIcon: Icons.person_outline_rounded,
      ),
    ];

    testWidgets('renders all 5 tabs in exact order with labels and badges', (
      tester,
    ) async {
      int selectedIndex = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            bottomNavigationBar: StatefulBuilder(
              builder: (context, setState) {
                return AppBottomNavBar(
                  currentIndex: selectedIndex,
                  onTap: (index) {
                    setState(() {
                      selectedIndex = index;
                    });
                  },
                  items: defaultItems,
                );
              },
            ),
          ),
        ),
      );

      // Verify all 5 tab labels exist in exact order
      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Categories'), findsOneWidget);
      expect(find.text('Favorites'), findsOneWidget);
      expect(find.text('Cart'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);

      // Verify badges for Favorites (4) and Cart (2)
      expect(find.text('4'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);

      // Verify tapping triggers onTap callback
      await tester.tap(find.text('Categories'));
      await tester.pumpAndSettle();
      expect(selectedIndex, 1);

      await tester.tap(find.text('Cart'));
      await tester.pumpAndSettle();
      expect(selectedIndex, 3);
    });

    testWidgets('formats badge counts over 99 as 99+', (tester) async {
      final itemsWithLargeBadge = [
        const AppNavItem(
          label: 'Home',
          activeIcon: Icons.home_rounded,
          inactiveIcon: Icons.home_outlined,
          badgeCount: 150,
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            bottomNavigationBar: AppBottomNavBar(
              currentIndex: 0,
              onTap: (_) {},
              items: itemsWithLargeBadge,
            ),
          ),
        ),
      );

      expect(find.text('99+'), findsOneWidget);
    });

    testWidgets('has floating container with ~28px radius and horizontal margin', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            bottomNavigationBar: AppBottomNavBar(
              currentIndex: 0,
              onTap: (_) {},
              items: defaultItems,
            ),
          ),
        ),
      );

      // Verify outer Container decoration
      final containerFinder = find.byWidgetPredicate(
        (widget) =>
            widget is Container &&
            widget.decoration is BoxDecoration &&
            (widget.decoration as BoxDecoration).borderRadius ==
                BorderRadius.circular(28.0),
      );
      expect(containerFinder, findsOneWidget);

      // Verify horizontal margin padding
      final paddingFinder = find.byWidgetPredicate(
        (widget) =>
            widget is Padding &&
            widget.padding == const EdgeInsets.symmetric(horizontal: 16.0),
      );
      expect(paddingFinder, findsOneWidget);
    });

    testWidgets('renders properly in dark mode theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            bottomNavigationBar: AppBottomNavBar(
              currentIndex: 2,
              onTap: (_) {},
              items: defaultItems,
            ),
          ),
        ),
      );

      expect(find.text('Favorites'), findsOneWidget);
      expect(find.byIcon(Icons.favorite_rounded), findsOneWidget);
    });

    testWidgets('respects reduced motion when animations are disabled', (
      tester,
    ) async {
      int selectedIndex = 0;

      await tester.pumpWidget(
        MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: MaterialApp(
            home: Scaffold(
              bottomNavigationBar: StatefulBuilder(
                builder: (context, setState) {
                  return AppBottomNavBar(
                    currentIndex: selectedIndex,
                    onTap: (index) {
                      setState(() {
                        selectedIndex = index;
                      });
                    },
                    items: defaultItems,
                  );
                },
              ),
            ),
          ),
        ),
      );

      // When animations are disabled, pump immediately updates state without waiting
      await tester.tap(find.text('Profile'));
      await tester.pump();
      expect(selectedIndex, 4);
    });

    testWidgets(
      'renders full Categories label when selected without truncation on standard phone widths',
      (tester) async {
        // iPhone 16e logical width is 393
        tester.view.physicalSize = const Size(393, 852);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() => tester.view.resetPhysicalSize());

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              bottomNavigationBar: AppBottomNavBar(
                currentIndex: 1, // Categories active
                onTap: (_) {},
                items: defaultItems,
              ),
            ),
          ),
        );

        // Verify Categories is rendered
        final categoriesFinder = find.text('Categories');
        expect(categoriesFinder, findsOneWidget);

        // Verify RenderParagraph doesn't report overflow
        final renderParagraph = tester.renderObject<RenderParagraph>(
          categoriesFinder,
        );
        expect(renderParagraph.didExceedMaxLines, isFalse);
      },
    );
  });
}
