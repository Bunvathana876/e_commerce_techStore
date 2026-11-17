import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/utils/page_transitions.dart';
import '../../../shared/widgets/bouncing_button.dart';
import '../../cart/providers/cart_provider.dart';
import '../providers/checkout_provider.dart';
import '../widgets/checkout_address_section.dart';
import '../../orders/providers/order_provider.dart';
import '../../orders/services/order_api_service.dart';
import 'order_success_screen.dart';

/// Professional checkout screen for Blue Panda.
/// Organizes checkout into 5 clear sections:
/// 1. Delivery Address (with selection modal)
/// 2. Order Items Review
/// 3. Shipping Method (aligned with CartProvider shipping rules)
/// 4. Payment Method
/// 5. Price Breakdown & Secure Place Order Action
class CheckoutScreen extends StatefulWidget {
  final OrderApiService? orderApiService;

  const CheckoutScreen({super.key, this.orderApiService});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  late final OrderApiService _orderApiService;
  late final CheckoutProvider _checkout;

  // Selected Payment Method: 0 = ABA KHQR (Demo), 1 = Card (Demo), 2 = COD
  int _selectedPaymentIndex = 2;
  final List<Map<String, dynamic>> _paymentMethods = const [
    {
      'name': 'ABA / KHQR Pay',
      'subtitle': 'Demo preview — payment remains pending until verified',
      'icon': Icons.qr_code_scanner_rounded,
      'color': Color(0xFF005A9C),
      'isDemo': true,
    },
    {
      'name': 'Credit / Debit Card',
      'subtitle': 'Demo preview — online card gateway not integrated',
      'icon': Icons.credit_card_rounded,
      'color': Color(0xFF2563EB),
      'isDemo': true,
    },
    {
      'name': 'Cash on Delivery (COD)',
      'subtitle': 'Pay cash when package arrives',
      'icon': Icons.payments_outlined,
      'color': Color(0xFF10B981),
      'isDemo': false,
    },
  ];

  bool _isPlacingOrder = false;

  @override
  void initState() {
    super.initState();
    _orderApiService = widget.orderApiService ?? OrderApiService();
    _checkout = CheckoutProvider(orders: _orderApiService);
    _checkout.addListener(_refreshCheckout);
    _checkout.load();
  }

  void _refreshCheckout() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _checkout.removeListener(_refreshCheckout);
    _checkout.dispose();
    super.dispose();
  }

  Future<void> _handlePlaceOrder(CartProvider cartProvider) async {
    if (_isPlacingOrder || _checkout.isLoading) return;
    if (!_orderApiService.client.isAuthenticated) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please sign in to place an order.')),
      );
      return;
    }
    setState(() => _isPlacingOrder = true);
    try {
      final checkoutItems = cartProvider.items
          .map(
            (i) => <String, dynamic>{
              'product_id': i.product.id,
              'quantity': i.quantity,
            },
          )
          .toList();
      final createdOrder = await _checkout.submit(
        items: checkoutItems,
        paymentMethod: _paymentMethods[_selectedPaymentIndex]['name'] as String,
        couponCode: cartProvider.appliedCouponCode,
      );
      if (!mounted || !_checkout.sessionCurrent || createdOrder == null) return;

      // Replaying an earlier order must not erase a newly edited cart.
      final orderedItems = _checkout.pending!.items;
      Map<int, int> quantities(List<Map<String, dynamic>> items) {
        final result = <int, int>{};
        for (final item in items) {
          final id = item['product_id'] as int;
          result[id] = (result[id] ?? 0) + (item['quantity'] as int);
        }
        return result;
      }

      final current = quantities(
        cartProvider.items
            .map(
              (i) => <String, dynamic>{
                'product_id': i.product.id,
                'quantity': i.quantity,
              },
            )
            .toList(),
      );
      final ordered = quantities(orderedItems);
      if (current.length == ordered.length &&
          current.entries.every((e) => ordered[e.key] == e.value)) {
        cartProvider.clearCart();
      }
      await _checkout.acknowledge();
      if (!mounted || !_checkout.sessionCurrent) return;
      context.read<OrderProvider?>()?.recordOrder(createdOrder);
      Navigator.of(context).pushReplacement(
        SmoothPageRoute(
          page: OrderSuccessScreen(
            grandTotal: createdOrder.total,
            paymentMethod: createdOrder.paymentMethod,
            paymentStatus: createdOrder.paymentStatus,
            addressCity: createdOrder.shippingAddress,
            orderId: createdOrder.formattedOrderId,
            order: createdOrder,
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              e is ApiException
                  ? e.message
                  : 'Unable to place order. Please check your connection and try again.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isPlacingOrder = false);
    }
  }

  void _showKhqrModal(BuildContext context, double totalAmount) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: isDark ? const Color(0xFF161F30) : Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Top drag indicator
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF475569)
                      : Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),

              // Demo KHQR header bar
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFD97706),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.info_outline_rounded,
                      color: Colors.white,
                      size: 20,
                    ),
                    SizedBox(width: 8),
                    Text(
                      'DEMO KHQR PREVIEW • UNVERIFIED',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                        fontSize: 12.5,
                        letterSpacing: 0.4,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              Text(
                'Blue Panda Official Store (Demo)',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                ),
              ),
              const SizedBox(height: 4),

              Text(
                '\$${totalAmount.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF2563EB),
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 16),

              // QR Code Graphic container
              Container(
                width: 200,
                height: 200,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: const Color(0xFFE2E8F0), width: 2),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.08),
                      blurRadius: 16,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // Corner positioning brackets
                    Positioned.fill(
                      child: CustomPaint(painter: _KhqrQrPatternPainter()),
                    ),
                    // Centered Store Badge
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: const Color(0xFF2563EB),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 3),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.15),
                            blurRadius: 6,
                          ),
                        ],
                      ),
                      child: const Center(
                        child: Icon(
                          Icons.shopping_bag_rounded,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),

              Text(
                'Online KHQR verification is not integrated yet. Scanning this demo QR does not process or confirm a payment.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 12,
                  height: 1.4,
                  fontWeight: FontWeight.w600,
                  color: isDark
                      ? const Color(0xFFCBD5E1)
                      : const Color(0xFF475569),
                ),
              ),
              const SizedBox(height: 20),

              BouncingButton(
                key: const Key('close_khqr_preview'),
                onTap: () => Navigator.pop(ctx),
                child: Container(
                  height: 48,
                  decoration: BoxDecoration(
                    color: const Color(0xFF2563EB),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  alignment: Alignment.center,
                  child: const Text(
                    'Close Preview',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final cartProvider = context.watch<CartProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final shippingCost = cartProvider.shippingFee;
    final discountedSubtotal =
        (cartProvider.subtotal - cartProvider.discountAmount).clamp(
          0.0,
          double.infinity,
        );
    final finalGrandTotal = discountedSubtotal + shippingCost;
    final bottomInset = MediaQuery.of(context).padding.bottom;

    return Scaffold(
      backgroundColor: isDark
          ? const Color(0xFF0B0F19)
          : const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: Text(
          'Checkout',
          style: TextStyle(
            fontWeight: FontWeight.w800,
            color: isDark ? Colors.white : const Color(0xFF0F172A),
            letterSpacing: -0.3,
          ),
        ),
        leading: IconButton(
          icon: Icon(
            Icons.arrow_back_ios_new_rounded,
            size: 18,
            color: isDark ? Colors.white : const Color(0xFF0F172A),
          ),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Stack(
        children: [
          // Scrollable checkout details
          ListView(
            padding: EdgeInsets.fromLTRB(16, 12, 16, 120 + bottomInset),
            physics: const BouncingScrollPhysics(),
            children: [
              // 1. Delivery Address Section
              _buildSectionHeader(
                'Delivery Address',
                icon: Icons.location_on_outlined,
                isDark: isDark,
              ),
              const SizedBox(height: 8),
              CheckoutAddressSection(checkout: _checkout),
              if (_checkout.pending != null) ...[
                const SizedBox(height: 12),
                Semantics(
                  liveRegion: true,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Previous checkout awaiting confirmation'),
                          const Text(
                            'Retry retrieves or completes this original order before you place another one.',
                          ),
                          Text(
                            _checkout.pending!.request['shipping_address']
                                as String,
                          ),
                          for (final item in _checkout.pending!.items)
                            Text(
                              'Product #${item['product_id']} × ${item['quantity']}',
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 18),

              // 2. Order Items Review Section
              _buildSectionHeader(
                'Order Items (${cartProvider.totalItemsCount})',
                icon: Icons.shopping_bag_outlined,
                isDark: isDark,
              ),
              const SizedBox(height: 8),
              _buildOrderItemsPreview(
                cartProvider: cartProvider,
                isDark: isDark,
              ),
              const SizedBox(height: 18),

              // 3. Shipping Method Section
              _buildSectionHeader(
                'Shipping Method',
                icon: Icons.local_shipping_outlined,
                isDark: isDark,
              ),
              const SizedBox(height: 8),
              _buildShippingMethodList(
                cartProvider: cartProvider,
                isDark: isDark,
              ),
              const SizedBox(height: 18),

              // 4. Payment Method Section
              _buildSectionHeader(
                'Payment Method',
                icon: Icons.payment_outlined,
                isDark: isDark,
              ),
              const SizedBox(height: 8),
              _buildPaymentMethodList(
                isDark: isDark,
                cartProvider: cartProvider,
                finalGrandTotal: finalGrandTotal,
              ),
              const SizedBox(height: 18),

              // 5. Price Breakdown Section
              _buildSectionHeader(
                'Price Breakdown',
                icon: Icons.receipt_long_outlined,
                isDark: isDark,
              ),
              const SizedBox(height: 8),
              _buildPriceBreakdownCard(
                cartProvider: cartProvider,
                shippingCost: shippingCost,
                finalGrandTotal: finalGrandTotal,
                isDark: isDark,
              ),
            ],
          ),

          // Sticky Bottom Place Order Action Bar
          Align(
            alignment: Alignment.bottomCenter,
            child: _buildStickyPlaceOrderBar(
              cartProvider: cartProvider,
              finalGrandTotal: finalGrandTotal,
              isDark: isDark,
            ),
          ),
        ],
      ),
    );
  }

  // Section title with icon
  Widget _buildSectionHeader(
    String title, {
    required IconData icon,
    bool isDark = false,
  }) {
    return Row(
      children: [
        Icon(icon, size: 17, color: const Color(0xFF2563EB)),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            title,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w800,
              color: isDark ? Colors.white : const Color(0xFF0F172A),
              letterSpacing: -0.2,
            ),
          ),
        ),
      ],
    );
  }

  // 2. Order items preview list
  Widget _buildOrderItemsPreview({
    required CartProvider cartProvider,
    required bool isDark,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161F30) : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isDark ? const Color(0xFF253248) : const Color(0xFFE2E8F0),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.2 : 0.03),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: List.generate(cartProvider.items.length, (index) {
          final item = cartProvider.items[index];
          final isLast = index == cartProvider.items.length - 1;

          return Padding(
            padding: EdgeInsets.only(bottom: isLast ? 0 : 10),
            child: Row(
              children: [
                // Thumbnail
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Container(
                    width: 48,
                    height: 48,
                    color: isDark
                        ? const Color(0xFF0F172A)
                        : const Color(0xFFF1F5F9),
                    child: item.product.imageUrl.isEmpty
                        ? Icon(
                            Icons.inventory_2_outlined,
                            size: 20,
                            color: isDark
                                ? const Color(0xFF64748B)
                                : const Color(0xFF94A3B8),
                          )
                        : Image.network(
                            item.product.imageUrl,
                            fit: BoxFit.contain,
                            errorBuilder: (_, _, _) => Icon(
                              Icons.broken_image_rounded,
                              size: 20,
                              color: isDark
                                  ? const Color(0xFF64748B)
                                  : const Color(0xFF94A3B8),
                            ),
                          ),
                  ),
                ),
                const SizedBox(width: 12),

                // Name and Quantity
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.product.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: isDark
                              ? Colors.white
                              : const Color(0xFF0F172A),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Qty: ${item.quantity} × \$${item.product.price.toStringAsFixed(2)}',
                        style: TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w500,
                          color: isDark
                              ? const Color(0xFF94A3B8)
                              : const Color(0xFF64748B),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),

                // Line Total
                Text(
                  '\$${item.totalPrice.toStringAsFixed(2)}',
                  style: const TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF2563EB),
                  ),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }

  // 3. Shipping method selection list
  Widget _buildShippingMethodList({
    required CartProvider cartProvider,
    required bool isDark,
  }) {
    final standardFee = cartProvider.shippingFee;

    final methods = [
      {
        'title': 'Standard Delivery',
        'subtitle': standardFee == 0.0
            ? 'Free shipping on orders of \$100 or more'
            : 'Standard shipping — final total confirmed by server',
        'price': standardFee,
      },
      {
        'title': 'Express Fast Delivery',
        'subtitle': 'Not available yet',
        'price': 0.0,
      },
    ];

    return Column(
      children: List.generate(methods.length, (index) {
        final method = methods[index];
        final isSelected = index == 0;
        final price = method['price'] as double;

        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: BouncingButton(
            key: Key('shipping_method_$index'),
            onTap: null,
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isSelected
                    ? const Color(
                        0xFF2563EB,
                      ).withValues(alpha: isDark ? 0.16 : 0.05)
                    : (isDark ? const Color(0xFF161F30) : Colors.white),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected
                      ? const Color(0xFF2563EB)
                      : (isDark
                            ? const Color(0xFF253248)
                            : const Color(0xFFE2E8F0)),
                  width: isSelected ? 1.8 : 1.2,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: isDark ? 0.15 : 0.02),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Icon(
                    isSelected
                        ? Icons.radio_button_checked
                        : Icons.radio_button_off,
                    color: isSelected
                        ? const Color(0xFF2563EB)
                        : (isDark
                              ? const Color(0xFF64748B)
                              : Colors.grey.shade400),
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          method['title'] as String,
                          style: TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                            color: isDark
                                ? Colors.white
                                : const Color(0xFF0F172A),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          method['subtitle'] as String,
                          style: TextStyle(
                            fontSize: 11.5,
                            color: isDark
                                ? Colors.grey.shade400
                                : Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    index == 1
                        ? 'Unavailable'
                        : (price == 0.0
                              ? 'FREE'
                              : '\$${price.toStringAsFixed(2)}'),
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w800,
                      color: index == 1
                          ? Theme.of(context).colorScheme.onSurfaceVariant
                          : price == 0.0
                          ? const Color(0xFF10B981)
                          : (isDark ? Colors.white : const Color(0xFF0F172A)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }

  // 4. Payment method selection list
  Widget _buildPaymentMethodList({
    required bool isDark,
    required CartProvider cartProvider,
    required double finalGrandTotal,
  }) {
    return Column(
      children: List.generate(_paymentMethods.length, (index) {
        final pay = _paymentMethods[index];
        final isSelected = _selectedPaymentIndex == index;

        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Column(
            children: [
              BouncingButton(
                key: Key('payment_method_$index'),
                onTap: _isPlacingOrder || _checkout.pending != null
                    ? null
                    : () => setState(() => _selectedPaymentIndex = index),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? const Color(
                            0xFF2563EB,
                          ).withValues(alpha: isDark ? 0.16 : 0.05)
                        : (isDark ? const Color(0xFF161F30) : Colors.white),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: isSelected
                          ? const Color(0xFF2563EB)
                          : (isDark
                                ? const Color(0xFF253248)
                                : const Color(0xFFE2E8F0)),
                      width: isSelected ? 1.8 : 1.2,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(
                          alpha: isDark ? 0.15 : 0.02,
                        ),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Icon(
                        isSelected
                            ? Icons.radio_button_checked
                            : Icons.radio_button_off,
                        color: isSelected
                            ? const Color(0xFF2563EB)
                            : (isDark
                                  ? const Color(0xFF64748B)
                                  : Colors.grey.shade400),
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: (pay['color'] as Color).withValues(
                            alpha: isDark ? 0.22 : 0.10,
                          ),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          pay['icon'] as IconData,
                          size: 20,
                          color: pay['color'] as Color,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    pay['name'] as String,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 13.5,
                                      fontWeight: FontWeight.w700,
                                      color: isDark
                                          ? Colors.white
                                          : const Color(0xFF0F172A),
                                    ),
                                  ),
                                ),
                                if (pay['isDemo'] == true) ...[
                                  const SizedBox(width: 6),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 6,
                                      vertical: 2,
                                    ),
                                    decoration: BoxDecoration(
                                      color: const Color(
                                        0xFFD97706,
                                      ).withValues(alpha: isDark ? 0.25 : 0.12),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: const Text(
                                      'DEMO',
                                      style: TextStyle(
                                        fontSize: 9.5,
                                        fontWeight: FontWeight.w800,
                                        color: Color(0xFFD97706),
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                            const SizedBox(height: 2),
                            Text(
                              pay['subtitle'] as String,
                              style: TextStyle(
                                fontSize: 11.5,
                                color: isDark
                                    ? Colors.grey.shade400
                                    : Colors.grey.shade600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (index == 0 && isSelected) ...[
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(
                      0xFF005A9C,
                    ).withValues(alpha: isDark ? 0.22 : 0.08),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: const Color(0xFF005A9C).withValues(alpha: 0.25),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.qr_code_2_rounded,
                        size: 22,
                        color: Color(0xFF005A9C),
                      ),
                      const SizedBox(width: 10),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'KHQR Demo Preview (Unverified)',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                                color: Color(0xFF005A9C),
                              ),
                            ),
                            Text(
                              'Online payment verification is not integrated yet',
                              style: TextStyle(
                                fontSize: 11,
                                color: Color(0xFF64748B),
                              ),
                            ),
                          ],
                        ),
                      ),
                      BouncingButton(
                        key: const Key('open_khqr_modal_button'),
                        onTap: () => _showKhqrModal(context, finalGrandTotal),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFF005A9C),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Text(
                            'Preview QR',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 11.5,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        );
      }),
    );
  }

  // 5. Price breakdown card
  Widget _buildPriceBreakdownCard({
    required CartProvider cartProvider,
    required double shippingCost,
    required double finalGrandTotal,
    required bool isDark,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161F30) : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isDark ? const Color(0xFF253248) : const Color(0xFFE2E8F0),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.2 : 0.03),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          _priceRow(
            'Cart Subtotal',
            '\$${cartProvider.subtotal.toStringAsFixed(2)}',
            isDark: isDark,
          ),
          if (cartProvider.hasCoupon) ...[
            const SizedBox(height: 8),
            _priceRow(
              'Promo Discount (${cartProvider.appliedCouponCode})',
              '-\$${cartProvider.discountAmount.toStringAsFixed(2)}',
              valueColor: const Color(0xFF10B981),
              isDark: isDark,
            ),
          ],
          const SizedBox(height: 8),
          _priceRow(
            'Shipping Fee',
            shippingCost == 0.0
                ? 'FREE'
                : '\$${shippingCost.toStringAsFixed(2)}',
            valueColor: shippingCost == 0.0 ? const Color(0xFF10B981) : null,
            isDark: isDark,
          ),
          Divider(
            height: 20,
            color: isDark ? const Color(0xFF253248) : const Color(0xFFF1F5F9),
          ),
          _priceRow(
            'Total Amount',
            '\$${finalGrandTotal.toStringAsFixed(2)}',
            isBold: true,
            isDark: isDark,
          ),
        ],
      ),
    );
  }

  // Sticky bottom place order button
  Widget _buildStickyPlaceOrderBar({
    required CartProvider cartProvider,
    required double finalGrandTotal,
    required bool isDark,
  }) {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 16),
          decoration: BoxDecoration(
            color: isDark
                ? const Color(0xFF161F30).withValues(alpha: 0.94)
                : Colors.white.withValues(alpha: 0.95),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            border: Border(
              top: BorderSide(
                color: isDark
                    ? const Color(0xFF253248).withValues(alpha: 0.8)
                    : const Color(0xFFE2E8F0),
                width: 1.2,
              ),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.35 : 0.08),
                blurRadius: 20,
                offset: const Offset(0, -4),
              ),
            ],
          ),
          child: SafeArea(
            top: false,
            child: BouncingButton(
              key: const Key('place_order_button'),
              onTap: _isPlacingOrder || _checkout.isLoading
                  ? null
                  : () => _handlePlaceOrder(cartProvider),
              child: Container(
                height: 52,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF2563EB), Color(0xFF1565C0)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF2563EB).withValues(alpha: 0.38),
                      blurRadius: 14,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                alignment: Alignment.center,
                child: _isPlacingOrder
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: Colors.white,
                        ),
                      )
                    : Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(
                                Icons.lock_outline_rounded,
                                color: Colors.white,
                                size: 18,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                _checkout.pending != null
                                    ? 'Retry pending order'
                                    : 'Place Order • \$${finalGrandTotal.toStringAsFixed(2)}',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.2,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _priceRow(
    String label,
    String value, {
    bool isBold = false,
    Color? valueColor,
    bool isDark = false,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: isBold ? 15 : 13,
            fontWeight: isBold ? FontWeight.w800 : FontWeight.w500,
            color: isBold
                ? (isDark ? Colors.white : const Color(0xFF0F172A))
                : (isDark ? Colors.grey.shade400 : const Color(0xFF64748B)),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.end,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: isBold ? 17 : 13.5,
              fontWeight: isBold ? FontWeight.w900 : FontWeight.w700,
              color:
                  valueColor ??
                  (isBold
                      ? (isDark ? Colors.white : const Color(0xFF0F172A))
                      : (isDark ? Colors.white : const Color(0xFF1E293B))),
            ),
          ),
        ),
      ],
    );
  }
}

/// Custom painter rendering high-contrast Cambodian Bakong KHQR pattern
class _KhqrQrPatternPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF0F172A)
      ..style = PaintingStyle.fill;

    // Corner finder patterns (Standard ISO QR position marks)
    void drawFinder(double x, double y) {
      canvas.drawRect(Rect.fromLTWH(x, y, 36, 36), paint);
      canvas.drawRect(
        Rect.fromLTWH(x + 5, y + 5, 26, 26),
        Paint()..color = Colors.white,
      );
      canvas.drawRect(Rect.fromLTWH(x + 10, y + 10, 16, 16), paint);
    }

    drawFinder(4, 4);
    drawFinder(size.width - 40, 4);
    drawFinder(4, size.height - 40);

    // Simulated authentic QR data modules
    final dotPaint = Paint()..color = const Color(0xFF1E293B);
    const step = 8.0;
    for (double x = 46; x < size.width - 46; x += step) {
      for (double y = 4; y < size.height; y += step) {
        if ((x.toInt() * 7 + y.toInt() * 13) % 5 == 0) {
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(x, y, 5, 5),
              const Radius.circular(1.5),
            ),
            dotPaint,
          );
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
