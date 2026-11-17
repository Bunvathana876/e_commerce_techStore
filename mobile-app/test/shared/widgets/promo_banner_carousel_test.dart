import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:e_commerc_mobile_app/shared/widgets/promo_banner_carousel.dart';
import 'package:e_commerc_mobile_app/shared/widgets/promo_banner.dart';

void main() {
  final testItems = [
    const PromoItem(
      titlePrefix: 'Get ',
      highlightText: '40% off',
      titleSuffix: ' your\nfirst order',
      subtitle: '+ \$0 delivery fee on orders \$15+',
      couponCode: 'FIRST40',
      buttonText: 'Order now',
    ),
    const PromoItem(
      titlePrefix: 'Up to ',
      highlightText: '50% off',
      titleSuffix: ' all\nelectronics',
      subtitle: 'Top tech & laptops',
      couponCode: 'TECH50',
      buttonText: 'Shop now',
      accentColor: Color(0xFF1E88E5),
    ),
    const PromoItem(
      titlePrefix: 'Flat ',
      highlightText: '30% off',
      titleSuffix: ' trending\nsneakers',
      subtitle: 'New sport drops',
      couponCode: 'KICKS30',
      buttonText: 'Explore',
      accentColor: Color(0xFFEA580C),
    ),
  ];

  Widget buildCarousel({
    List<PromoItem>? items,
    Duration autoScrollDuration = const Duration(seconds: 4),
  }) {
    return MaterialApp(
      home: Scaffold(
        body: PromoBannerCarousel(
          items: items ?? testItems,
          autoScrollDuration: autoScrollDuration,
        ),
      ),
    );
  }

  testWidgets('PromoBannerCarousel renders initial item and dots properly', (
    tester,
  ) async {
    await tester.pumpWidget(buildCarousel());
    await tester.pumpAndSettle();

    // Verify initial item is visible
    expect(find.textContaining('40% off', findRichText: true), findsOneWidget);
    expect(find.textContaining('FIRST40'), findsNothing);
    expect(find.text('Order now'), findsOneWidget);

    // Verify PromoBanner has activeDotIndex = 0 and totalDots = 3
    final bannerFinder = find.byType(PromoBanner);
    expect(bannerFinder, findsOneWidget);
    final banner = tester.widget<PromoBanner>(bannerFinder);
    expect(banner.activeDotIndex, 0);
    expect(banner.totalDots, 3);
  });

  testWidgets('PromoBannerCarousel auto-scrolls to next item after duration', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildCarousel(autoScrollDuration: const Duration(seconds: 4)),
    );
    await tester.pumpAndSettle();

    // Advance 4 seconds to trigger periodic timer
    await tester.pump(const Duration(seconds: 4));
    // Settle animation (Curves.easeInOutCubic, 650ms)
    await tester.pumpAndSettle();

    // Page 1 (Electronics 50% off) should now be active
    expect(find.textContaining('50% off', findRichText: true), findsOneWidget);
    expect(find.text('Shop now'), findsOneWidget);

    final banner = tester.widget<PromoBanner>(find.byType(PromoBanner));
    expect(banner.activeDotIndex, 1);

    // Advance another 4 seconds
    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();

    // Page 2 (Sneakers 30% off) should now be active
    expect(find.textContaining('30% off', findRichText: true), findsOneWidget);
    expect(find.text('Explore'), findsOneWidget);

    final banner2 = tester.widget<PromoBanner>(find.byType(PromoBanner));
    expect(banner2.activeDotIndex, 2);

    // Advance another 4 seconds to test circular wrap-around to page 0
    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();

    expect(find.textContaining('40% off', findRichText: true), findsOneWidget);
    final banner3 = tester.widget<PromoBanner>(find.byType(PromoBanner));
    expect(banner3.activeDotIndex, 0);
  });

  testWidgets(
    'Manual swipe changes page, resets timer, and updates activeDotIndex',
    (tester) async {
      await tester.pumpWidget(
        buildCarousel(autoScrollDuration: const Duration(seconds: 4)),
      );
      await tester.pumpAndSettle();

      expect(
        find.textContaining('40% off', findRichText: true),
        findsOneWidget,
      );

      // Swipe left to advance to next page manually
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();

      // Page 1 should now be active
      expect(
        find.textContaining('50% off', findRichText: true),
        findsOneWidget,
      );
      final banner = tester.widget<PromoBanner>(find.byType(PromoBanner));
      expect(banner.activeDotIndex, 1);

      // Wait 2 seconds (less than 4s autoScrollDuration) - should stay on page 1
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('50% off', findRichText: true),
        findsOneWidget,
      );

      // Wait another 2 seconds (reaching full 4s from reset) - auto-scroll to page 2
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('30% off', findRichText: true),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'PromoBannerCarousel cleans up resources on dispose without error',
    (tester) async {
      await tester.pumpWidget(buildCarousel());
      await tester.pumpAndSettle();

      // Unmount the widget to trigger dispose()
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: SizedBox())),
      );
      await tester.pumpAndSettle();

      expect(find.byType(PromoBannerCarousel), findsNothing);
    },
  );

  testWidgets('PromoBannerCarousel handles empty list gracefully', (
    tester,
  ) async {
    await tester.pumpWidget(buildCarousel(items: []));
    await tester.pumpAndSettle();

    expect(find.byType(PromoBanner), findsNothing);
  });

  testWidgets('PromoBanner renders tag and badge when provided', (
    tester,
  ) async {
    const customItem = PromoItem(
      titlePrefix: 'Special ',
      highlightText: '25% off',
      titleSuffix: ' today',
      couponCode: 'SAVE25',
      tag: 'FLASH DEAL',
      tagIcon: Icons.bolt_rounded,
      badgeText: 'HOT',
    );

    await tester.pumpWidget(buildCarousel(items: [customItem]));
    await tester.pumpAndSettle();

    expect(find.text('FLASH DEAL'), findsOneWidget);
    expect(find.byIcon(Icons.bolt_rounded), findsOneWidget);
    expect(find.text('HOT'), findsOneWidget);
  });

  testWidgets('PromoBanner does not render promocode chips keeping UI clean', (
    tester,
  ) async {
    const customItem = PromoItem(
      highlightText: '10% off',
      couponCode: 'WELCOME10',
    );

    await tester.pumpWidget(buildCarousel(items: [customItem]));
    await tester.pumpAndSettle();

    // Verify coupon code is not rendered anywhere in the banner UI
    expect(find.textContaining('WELCOME10'), findsNothing);
    expect(find.textContaining('Code:'), findsNothing);
  });

  testWidgets('Tapping CTA button triggers onTap callback', (
    tester,
  ) async {
    var tapped = false;
    final customItem = PromoItem(
      highlightText: '10% off',
      buttonText: 'Shop now',
      onTap: () => tapped = true,
    );

    await tester.pumpWidget(buildCarousel(items: [customItem]));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Shop now'));
    await tester.pumpAndSettle();

    expect(tapped, isTrue);
  });

  testWidgets('PromoBanner renders full-bleed editorial layout with gradient overlay', (
    tester,
  ) async {
    const customItem = PromoItem(
      titlePrefix: 'Curated ',
      highlightText: 'Summer ',
      titleSuffix: 'Styles',
      subtitle: 'Minimal essentials & fresh apparel',
      buttonText: 'Discover',
      tag: 'NEW COLLECTION',
      badgeText: 'FEATURED',
      imageUrl: 'https://images.unsplash.com/photo-1441986300917-64674bd600d8',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.light(),
        home: Scaffold(
          body: PromoBanner(
            titlePrefix: customItem.titlePrefix,
            highlightText: customItem.highlightText,
            titleSuffix: customItem.titleSuffix,
            subtitle: customItem.subtitle,
            buttonText: customItem.buttonText,
            tag: customItem.tag,
            badgeText: customItem.badgeText,
            imageUrl: customItem.imageUrl,
            totalDots: 3,
            activeDotIndex: 0,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Verify ClipRRect with radius 24
    final clipRRectFinder = find.descendant(
      of: find.byType(PromoBanner),
      matching: find.byType(ClipRRect),
    );
    expect(clipRRectFinder, findsOneWidget);
    final clipRRect = tester.widget<ClipRRect>(clipRRectFinder);
    expect(clipRRect.borderRadius, BorderRadius.circular(24));

    // Verify directional gradient overlay DecoratedBox exists
    final decoratedBoxes = tester.widgetList<DecoratedBox>(
      find.descendant(
        of: find.byType(PromoBanner),
        matching: find.byType(DecoratedBox),
      ),
    );
    final hasDirectionalGradient = decoratedBoxes.any((box) {
      final decoration = box.decoration;
      if (decoration is BoxDecoration && decoration.gradient is LinearGradient) {
        final gradient = decoration.gradient as LinearGradient;
        return gradient.begin == Alignment.centerLeft &&
            gradient.end == Alignment.centerRight;
      }
      return false;
    });
    expect(hasDirectionalGradient, isTrue);

    // Verify CTA button with capsule border radius and arrow icon
    expect(find.text('Discover'), findsOneWidget);
    expect(find.byIcon(Icons.arrow_forward_rounded), findsOneWidget);

    // Verify badge
    expect(find.text('FEATURED'), findsOneWidget);
    // Verify tag
    expect(find.text('NEW COLLECTION'), findsOneWidget);
  });

  testWidgets('PromoBanner dark mode renders high-contrast surfaces and colors', (
    tester,
  ) async {
    const customItem = PromoItem(
      title: 'Dark Mode Banner',
      subtitle: 'Testing dark mode contrast',
      buttonText: 'Shop Dark',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(),
        home: Scaffold(
          body: PromoBanner(
            title: customItem.title,
            subtitle: customItem.subtitle,
            buttonText: customItem.buttonText,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Dark Mode Banner'), findsOneWidget);
    expect(find.text('Shop Dark'), findsOneWidget);

    // Verify white CTA pill background in dark mode
    final ctaContainerFinder = find.ancestor(
      of: find.text('Shop Dark'),
      matching: find.byType(Container),
    );
    expect(ctaContainerFinder, findsWidgets);
    final ctaContainer = tester.widget<Container>(ctaContainerFinder.first);
    final boxDecoration = ctaContainer.decoration as BoxDecoration;
    expect(boxDecoration.color, Colors.white);
  });

  testWidgets('PromoBanner handles empty image URL gracefully with fallback icon', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: PromoBanner(
            title: 'No Image Banner',
            subtitle: 'Graceful fallback test',
            imageUrl: null,
            assetPath: null,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Verify shopping bag fallback icon is rendered
    expect(find.byIcon(Icons.shopping_bag_outlined), findsOneWidget);
  });

  testWidgets('PromoBannerCarousel respects MediaQuery.disableAnimations for a11y', (
    tester,
  ) async {
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: buildCarousel(autoScrollDuration: const Duration(seconds: 4)),
      ),
    );
    await tester.pumpAndSettle();

    // Wait 4 seconds - with disableAnimations: true, it should NOT auto-advance
    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();

    // Should still be on page 0
    final banner = tester.widget<PromoBanner>(find.byType(PromoBanner));
    expect(banner.activeDotIndex, 0);
  });
}
