import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/cart/providers/cart_provider.dart';
import 'package:e_commerc_mobile_app/features/cart/screens/cart_screen.dart';
import 'package:e_commerc_mobile_app/features/checkout/screens/checkout_screen.dart';
import 'package:e_commerc_mobile_app/features/checkout/screens/order_success_screen.dart';
import 'package:e_commerc_mobile_app/features/orders/models/order_model.dart';
import 'package:e_commerc_mobile_app/features/orders/screens/order_detail_screen.dart';
import 'package:e_commerc_mobile_app/features/orders/screens/order_tracking_screen.dart';
import 'package:e_commerc_mobile_app/features/products/models/product_model.dart';

void main() {
  const testProduct = ProductModel(
    id: 101,
    name: 'UltraBook Pro 15" M2 Laptop',
    description: 'High performance laptop with retina display.',
    price: 100.00,
    rating: 4.9,
    reviewCount: 312,
    categoryId: 1,
    imageUrl: '',
  );

  final testOrder = OrderModel(
    id: 1001,
    userId: 1,
    status: 'shipped',
    subtotal: 100.00,
    discountAmount: 10.00,
    couponCode: 'WELCOME10',
    shippingFee: 0.00,
    total: 90.00,
    paymentMethod: 'Credit / Debit Card',
    paymentStatus: 'paid',
    shippingAddress: 'Bun Vathana (+855 12 345 678)\nBuilding #45, St. 2004, Sen Sok, Phnom Penh, Cambodia',
    createdAt: DateTime.now(),
    items: const [
      OrderItemModel(
        id: 1,
        orderId: 1001,
        productId: 101,
        productName: 'UltraBook Pro 15" M2 Laptop',
        price: 100.00,
        quantity: 1,
        subtotal: 100.00,
      ),
    ],
  );

  group('CartProvider Explicit Demo Promo Code Tests', () {
    test('applies percentage coupon WELCOME10 in explicit demo mode', () async {
      final cart = CartProvider(useRemoteBackend: false);
      cart.addItem(testProduct, quantity: 1); // subtotal = $100

      expect(cart.hasCoupon, isFalse);
      expect(cart.grandTotal, 100.0); // >= 100 -> free shipping

      final success = await cart.applyCoupon('WELCOME10');
      expect(success, isTrue);
      expect(cart.hasCoupon, isTrue);
      expect(cart.appliedCouponCode, 'WELCOME10');
      expect(cart.discountAmount, 10.0); // 10% of 100
      expect(cart.grandTotal, 90.0); // 100 - 10 + 0

      cart.removeCoupon();
      expect(cart.hasCoupon, isFalse);
      expect(cart.grandTotal, 100.0);
    });

    test('rejects promo code if minimum spend is not met in explicit demo mode', () async {
      final cart = CartProvider(useRemoteBackend: false);
      const cheapItem = ProductModel(
        id: 102,
        name: 'USB-C Cable',
        description: 'Durable nylon cable',
        price: 15.00,
        rating: 4.5,
        reviewCount: 12,
        categoryId: 1,
        imageUrl: '',
      );
      cart.addItem(cheapItem, quantity: 1); // subtotal = $15

      // SAVE20 requires minimum order of $50
      final success = await cart.applyCoupon('SAVE20');
      expect(success, isFalse);
      expect(cart.hasCoupon, isFalse);
      expect(cart.couponErrorMessage, contains('requires a minimum order of \$50.00'));
    });

    test('rejects non-existent promo code in explicit demo mode', () async {
      final cart = CartProvider(useRemoteBackend: false);
      cart.addItem(testProduct, quantity: 1);

      final success = await cart.applyCoupon('INVALID999');
      expect(success, isFalse);
      expect(cart.hasCoupon, isFalse);
      expect(cart.couponErrorMessage, contains("Promo code 'INVALID999' does not exist"));
    });
  });

  group('CartScreen Promo Code UI Tests', () {
    testWidgets('renders promo code voucher section and applies coupon in explicit demo mode', (
      WidgetTester tester,
    ) async {
      final cart = CartProvider(useRemoteBackend: false);
      cart.addItem(testProduct, quantity: 1);

      await tester.pumpWidget(
        ChangeNotifierProvider<CartProvider>.value(
          value: cart,
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const CartScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Promo Code & Voucher'), findsOneWidget);
      expect(find.byKey(const Key('coupon_text_field')), findsOneWidget);
      expect(find.byKey(const Key('apply_coupon_button')), findsOneWidget);

      // Enter promo code
      await tester.enterText(
        find.byKey(const Key('coupon_text_field')),
        'WELCOME10',
      );
      await tester.tap(find.byKey(const Key('apply_coupon_button')));
      await tester.pumpAndSettle();

      // Verify promo discount applied in UI
      expect(find.text('Promo Discount Applied'), findsOneWidget);
      expect(find.text('Promo Discount (WELCOME10)'), findsOneWidget);
      expect(find.text('-\$10.00'), findsOneWidget);
      expect(find.text('\$90.00'), findsWidgets); // updated grand total

      // Remove coupon
      await tester.tap(find.byKey(const Key('remove_coupon_button')));
      await tester.pumpAndSettle();

      expect(find.text('Promo Discount Applied'), findsNothing);
      expect(find.text('\$100.00'), findsWidgets);
    });
  });

  group('CheckoutScreen Payment Methods Restriction Tests', () {
    testWidgets('shows strictly Cash on Delivery (COD) and Credit / Debit Card with no KHQR preview', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 2.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final cart = CartProvider();
      cart.addItem(testProduct, quantity: 1);

      await tester.pumpWidget(
        ChangeNotifierProvider<CartProvider>.value(
          value: cart,
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const CheckoutScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('ABA / KHQR Pay'), findsNothing);
      expect(find.text('KHQR Demo Preview (Unverified)'), findsNothing);
      expect(find.byKey(const Key('open_khqr_modal_button')), findsNothing);
      expect(find.text('DEMO'), findsNothing);
      expect(find.text('Cash on Delivery (COD)'), findsOneWidget);
      expect(find.text('Credit / Debit Card'), findsOneWidget);

      await tester.tap(find.byKey(const Key('payment_method_1')));
      await tester.pumpAndSettle();
      expect(find.byType(OrderSuccessScreen), findsNothing);
      expect(cart.isEmpty, isFalse);
    });
  });

  group('OrderTrackingScreen Real Shipment Tracking Tests', () {
    testWidgets('navigates to OrderTrackingScreen from OrderSuccessScreen', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 2.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: OrderSuccessScreen(
            grandTotal: 90.0,
            paymentMethod: 'Credit / Debit Card',
            addressCity: 'Phnom Penh',
            orderId: testOrder.formattedOrderId,
            order: testOrder,
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byKey(const Key('track_delivery_button')), findsOneWidget);

      await tester.tap(find.byKey(const Key('track_delivery_button')));
      await tester.pumpAndSettle();

      // Verifies real OrderTrackingScreen elements with zero fabricated GPS or driver data
      expect(find.byType(OrderTrackingScreen), findsOneWidget);
      expect(find.text('Order Tracking'), findsOneWidget);
      expect(find.text('Shipment Details'), findsOneWidget);
      expect(find.text('Tracking Timeline'), findsOneWidget);
      expect(find.text('Package Summary'), findsOneWidget);
      expect(find.text('Live GPS Connected'), findsNothing);
      expect(find.text('Sokha Rith'), findsNothing);
      expect(find.byKey(const Key('call_driver_button')), findsNothing);
      expect(find.byKey(const Key('message_driver_button')), findsNothing);
    });

    testWidgets('navigates to OrderTrackingScreen from OrderDetailScreen', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 2.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: OrderDetailScreen(order: testOrder),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byKey(const Key('order_detail_track_delivery_button')), findsOneWidget);

      await tester.tap(find.byKey(const Key('order_detail_track_delivery_button')));
      await tester.pumpAndSettle();

      expect(find.byType(OrderTrackingScreen), findsOneWidget);
    });
  });
}
