import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/network/api_exceptions.dart';
import '../models/order_model.dart';
import '../models/order_tracking_model.dart';
import '../services/order_api_service.dart';

class OrderTrackingScreen extends StatefulWidget {
  final OrderModel order;
  final OrderApiService? orderApiService;

  const OrderTrackingScreen({
    super.key,
    required this.order,
    this.orderApiService,
  });

  @override
  State<OrderTrackingScreen> createState() => _OrderTrackingScreenState();
}

class _OrderTrackingScreenState extends State<OrderTrackingScreen> {
  late final OrderApiService _orderService;
  bool _isLoading = true;
  String? _error;
  OrderTrackingData? _tracking;

  @override
  void initState() {
    super.initState();
    _orderService = widget.orderApiService ?? OrderApiService();
    _loadTracking();
  }

  Future<void> _loadTracking() async {
    if (mounted) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }
    try {
      final data = await _orderService.getOrderTracking(widget.order.id);
      if (!mounted) return;
      setState(() {
        _tracking = data;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e is ApiException
            ? e.message
            : 'Unable to load shipment tracking from the server.';
        _isLoading = false;
      });
    }
  }

  String _formatStatusLabel(String raw) {
    final normalized = raw.trim().replaceAll('_', ' ');
    if (normalized.isEmpty) return 'Pending';
    return normalized
        .split(' ')
        .where((w) => w.isNotEmpty)
        .map((w) => '${w[0].toUpperCase()}${w.substring(1).toLowerCase()}')
        .join(' ');
  }

  double _statusProgress(String rawStatus) {
    switch (rawStatus.toLowerCase()) {
      case 'pending':
      case 'label_created':
        return 0.20;
      case 'processing':
      case 'picked_up':
        return 0.45;
      case 'shipped':
      case 'in_transit':
        return 0.70;
      case 'out_for_delivery':
        return 0.88;
      case 'delivered':
        return 1.0;
      case 'cancelled':
      case 'failed_attempt':
      case 'returned':
        return 1.0;
      default:
        return 0.30;
    }
  }

  Color _statusAccent(String rawStatus) {
    switch (rawStatus.toLowerCase()) {
      case 'delivered':
        return const Color(0xFF10B981);
      case 'cancelled':
      case 'failed_attempt':
      case 'returned':
        return const Color(0xFFEF4444);
      case 'out_for_delivery':
      case 'in_transit':
      case 'shipped':
        return const Color(0xFF2563EB);
      default:
        return const Color(0xFFF59E0B);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC);
    final cardBg = isDark ? const Color(0xFF161F30) : Colors.white;
    final borderColor = isDark
        ? const Color(0xFF253248)
        : const Color(0xFFE2E8F0);
    final titleColor = isDark ? Colors.white : const Color(0xFF0F172A);
    final mutedColor = isDark
        ? const Color(0xFF94A3B8)
        : const Color(0xFF64748B);

    final effectiveStatus =
        _tracking?.shipment?.status ??
        _tracking?.orderStatus ??
        widget.order.status;
    final shipment = _tracking?.shipment;

    return Scaffold(
      backgroundColor: bgColor,
      appBar: AppBar(
        backgroundColor: cardBg,
        elevation: 0,
        leading: IconButton(
          icon: Icon(
            Icons.arrow_back_ios_new_rounded,
            size: 18,
            color: titleColor,
          ),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text(
          'Order Tracking',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: titleColor,
          ),
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh tracking',
            onPressed: _isLoading ? null : _loadTracking,
            icon: Icon(Icons.refresh_rounded, color: titleColor),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadTracking,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          children: [
            _buildStatusHeaderCard(
              cardBg: cardBg,
              borderColor: borderColor,
              titleColor: titleColor,
              mutedColor: mutedColor,
              isDark: isDark,
              effectiveStatus: effectiveStatus,
              shipment: shipment,
            ),
            const SizedBox(height: 16),
            if (_error != null) ...[
              _buildErrorBanner(cardBg: cardBg, titleColor: titleColor),
              const SizedBox(height: 16),
            ],
            _buildCarrierCard(
              cardBg: cardBg,
              borderColor: borderColor,
              titleColor: titleColor,
              mutedColor: mutedColor,
              isDark: isDark,
              shipment: shipment,
            ),
            const SizedBox(height: 16),
            _buildTimelineCard(
              cardBg: cardBg,
              borderColor: borderColor,
              titleColor: titleColor,
              mutedColor: mutedColor,
              isDark: isDark,
            ),
            const SizedBox(height: 16),
            _buildPackageDetailsCard(
              cardBg: cardBg,
              borderColor: borderColor,
              titleColor: titleColor,
              mutedColor: mutedColor,
              isDark: isDark,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusHeaderCard({
    required Color cardBg,
    required Color borderColor,
    required Color titleColor,
    required Color mutedColor,
    required bool isDark,
    required String effectiveStatus,
    required OrderShipmentModel? shipment,
  }) {
    final accent = _statusAccent(effectiveStatus);
    final eta = shipment?.estimatedDeliveryAt;
    final etaText = eta != null
        ? 'Estimated Delivery: ${_formatDate(eta)}'
        : shipment?.deliveredAt != null
        ? 'Delivered: ${_formatDate(shipment!.deliveredAt!)}'
        : _formatStatusLabel(effectiveStatus);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: isDark ? 0.2 : 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(Icons.local_shipping_rounded, color: accent),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      etaText,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: titleColor,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${widget.order.formattedOrderId} • Status: ${_formatStatusLabel(effectiveStatus)}',
                      style: TextStyle(fontSize: 12.5, color: mutedColor),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _statusProgress(effectiveStatus),
              minHeight: 7,
              backgroundColor: isDark
                  ? const Color(0xFF1E293B)
                  : const Color(0xFFE2E8F0),
              valueColor: AlwaysStoppedAnimation<Color>(accent),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorBanner({
    required Color cardBg,
    required Color titleColor,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_rounded, color: Color(0xFFDC2626)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              _error ?? 'Unable to reach tracking service.',
              style: const TextStyle(
                fontSize: 12.5,
                color: Color(0xFF991B1B),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          TextButton(
            onPressed: _loadTracking,
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildCarrierCard({
    required Color cardBg,
    required Color borderColor,
    required Color titleColor,
    required Color mutedColor,
    required bool isDark,
    required OrderShipmentModel? shipment,
  }) {
    final hasTrackingNum =
        shipment?.trackingNumber != null &&
        shipment!.trackingNumber!.trim().isNotEmpty;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Shipment Details',
            style: TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: titleColor,
            ),
          ),
          const SizedBox(height: 12),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Center(child: CircularProgressIndicator(strokeWidth: 2.2)),
            )
          else if (shipment == null)
            Text(
              'A carrier and tracking number will appear here once the seller or warehouse dispatches your package.',
              style: TextStyle(fontSize: 13, color: mutedColor, height: 1.4),
            )
          else ...[
            Row(
              children: [
                Text('Carrier:', style: TextStyle(fontSize: 13, color: mutedColor)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    shipment.carrier,
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      color: titleColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Text(
                  'Tracking ID:',
                  style: TextStyle(fontSize: 13, color: mutedColor),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    hasTrackingNum
                        ? shipment.trackingNumber!
                        : 'Pending assignment',
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      color: hasTrackingNum
                          ? const Color(0xFF2563EB)
                          : mutedColor,
                    ),
                  ),
                ),
                if (hasTrackingNum)
                  IconButton(
                    tooltip: 'Copy tracking number',
                    onPressed: () {
                      Clipboard.setData(
                        ClipboardData(text: shipment.trackingNumber!),
                      );
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Tracking number copied to clipboard'),
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    },
                    icon: const Icon(
                      Icons.copy_rounded,
                      size: 18,
                      color: Color(0xFF2563EB),
                    ),
                  ),
              ],
            ),
            if (shipment.notes != null && shipment.notes!.trim().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                shipment.notes!,
                style: TextStyle(fontSize: 12.5, color: mutedColor),
              ),
            ],
          ],
          const Divider(height: 24),
          Text(
            'Delivery Address',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: mutedColor,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            (_tracking?.shippingAddress.isNotEmpty == true)
                ? _tracking!.shippingAddress
                : widget.order.shippingAddress,
            style: TextStyle(fontSize: 13, color: titleColor, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineCard({
    required Color cardBg,
    required Color borderColor,
    required Color titleColor,
    required Color mutedColor,
    required bool isDark,
  }) {
    final events = _tracking?.events ?? const <OrderTrackingEventModel>[];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Tracking Timeline',
            style: TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: titleColor,
            ),
          ),
          const SizedBox(height: 14),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator(strokeWidth: 2.2)),
            )
          else if (events.isEmpty)
            Text(
              _error != null
                  ? 'Live timeline could not be loaded while offline. Current order status: ${_formatStatusLabel(widget.order.status)}.'
                  : 'Order placed — waiting for first fulfillment update (${_formatStatusLabel(widget.order.status)}).',
              style: TextStyle(fontSize: 13, color: mutedColor, height: 1.4),
            )
          else
            Column(
              children: List.generate(events.length, (index) {
                final event = events[index];
                final isLast = index == events.length - 1;
                final isFirst = index == 0;
                final dotColor = isFirst
                    ? const Color(0xFF2563EB)
                    : (isDark
                          ? const Color(0xFF64748B)
                          : const Color(0xFF94A3B8));
                final formattedDate = _formatDateTime(event.occurredAt);

                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Column(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          margin: const EdgeInsets.only(top: 4),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: dotColor,
                          ),
                        ),
                        if (!isLast)
                          Container(
                            width: 2,
                            height: 44,
                            color: isDark
                                ? const Color(0xFF334155)
                                : const Color(0xFFE2E8F0),
                          ),
                      ],
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Padding(
                        padding: EdgeInsets.only(bottom: isLast ? 0 : 14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              event.title,
                              style: TextStyle(
                                fontSize: 13.5,
                                fontWeight: FontWeight.w700,
                                color: titleColor,
                              ),
                            ),
                            if (event.description != null &&
                                event.description!.trim().isNotEmpty) ...[
                              const SizedBox(height: 2),
                              Text(
                                event.description!,
                                style: TextStyle(fontSize: 12.5, color: mutedColor),
                              ),
                            ],
                            const SizedBox(height: 3),
                            Text(
                              event.location != null &&
                                      event.location!.trim().isNotEmpty
                                  ? '$formattedDate • ${event.location}'
                                  : formattedDate,
                              style: TextStyle(fontSize: 11.5, color: mutedColor),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                );
              }),
            ),
        ],
      ),
    );
  }

  Widget _buildPackageDetailsCard({
    required Color cardBg,
    required Color borderColor,
    required Color titleColor,
    required Color mutedColor,
    required bool isDark,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Package Summary',
            style: TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: titleColor,
            ),
          ),
          const SizedBox(height: 12),
          for (final item in widget.order.items) ...[
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${item.productName} × ${item.quantity}',
                    style: TextStyle(fontSize: 13, color: titleColor),
                  ),
                ),
                Text(
                  '\$${item.subtotal.toStringAsFixed(2)}',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: titleColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
          ],
          const Divider(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Payment', style: TextStyle(fontSize: 13, color: mutedColor)),
              Text(
                '${widget.order.paymentMethod} (${_formatStatusLabel(_tracking?.paymentStatus ?? widget.order.paymentStatus)})',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: titleColor,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Order Total',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: titleColor,
                ),
              ),
              Text(
                '\$${widget.order.total.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: Color(0xFF2563EB),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  static const _months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${_months[local.month - 1]} ${local.day}, ${local.year}';
  }

  String _formatDateTime(DateTime dt) {
    final local = dt.toLocal();
    final hour12 = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour >= 12 ? 'PM' : 'AM';
    return '${_formatDate(local)} • $hour12:$minute $period';
  }
}
