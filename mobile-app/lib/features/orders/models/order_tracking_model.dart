class OrderShipmentModel {
  final int id;
  final int orderId;
  final String carrier;
  final String? trackingNumber;
  final String? trackingUrl;
  final String status;
  final DateTime? estimatedDeliveryAt;
  final DateTime? shippedAt;
  final DateTime? deliveredAt;
  final String? notes;
  final DateTime? updatedAt;

  const OrderShipmentModel({
    required this.id,
    required this.orderId,
    required this.carrier,
    this.trackingNumber,
    this.trackingUrl,
    required this.status,
    this.estimatedDeliveryAt,
    this.shippedAt,
    this.deliveredAt,
    this.notes,
    this.updatedAt,
  });

  factory OrderShipmentModel.fromJson(Map<String, dynamic> json) {
    return OrderShipmentModel(
      id: (json['id'] as num?)?.toInt() ?? 0,
      orderId: (json['order_id'] as num?)?.toInt() ?? 0,
      carrier: json['carrier']?.toString() ?? 'Standard Carrier',
      trackingNumber: json['tracking_number']?.toString(),
      trackingUrl: json['tracking_url']?.toString(),
      status: json['status']?.toString() ?? 'pending',
      estimatedDeliveryAt: _parseDate(json['estimated_delivery_at']),
      shippedAt: _parseDate(json['shipped_at']),
      deliveredAt: _parseDate(json['delivered_at']),
      notes: json['notes']?.toString(),
      updatedAt: _parseDate(json['updated_at']),
    );
  }
}

class OrderTrackingEventModel {
  final int? id;
  final String status;
  final String title;
  final String? description;
  final String? location;
  final DateTime occurredAt;

  const OrderTrackingEventModel({
    this.id,
    required this.status,
    required this.title,
    this.description,
    this.location,
    required this.occurredAt,
  });

  factory OrderTrackingEventModel.fromJson(Map<String, dynamic> json) {
    return OrderTrackingEventModel(
      id: (json['id'] as num?)?.toInt(),
      status: json['status']?.toString() ?? 'pending',
      title: json['title']?.toString() ?? 'Order update',
      description: json['description']?.toString(),
      location: json['location']?.toString(),
      occurredAt: _parseDate(json['occurred_at']) ?? DateTime.now(),
    );
  }
}

class OrderTrackingData {
  final int orderId;
  final String orderStatus;
  final String paymentStatus;
  final String shippingAddress;
  final bool hasShipmentRecord;
  final OrderShipmentModel? shipment;
  final List<OrderTrackingEventModel> events;

  const OrderTrackingData({
    required this.orderId,
    required this.orderStatus,
    required this.paymentStatus,
    required this.shippingAddress,
    required this.hasShipmentRecord,
    this.shipment,
    this.events = const [],
  });

  factory OrderTrackingData.fromJson(Map<String, dynamic> json) {
    final rawShipment = json['shipment'];
    final rawEvents = json['events'];
    return OrderTrackingData(
      orderId: (json['order_id'] as num?)?.toInt() ?? 0,
      orderStatus: json['order_status']?.toString() ?? 'pending',
      paymentStatus: json['payment_status']?.toString() ?? 'pending',
      shippingAddress: json['shipping_address']?.toString() ?? '',
      hasShipmentRecord: json['has_shipment_record'] == true,
      shipment: rawShipment is Map
          ? OrderShipmentModel.fromJson(Map<String, dynamic>.from(rawShipment))
          : null,
      events: rawEvents is List
          ? rawEvents
                .whereType<Map>()
                .map(
                  (e) => OrderTrackingEventModel.fromJson(
                    Map<String, dynamic>.from(e),
                  ),
                )
                .toList()
          : const [],
    );
  }
}

DateTime? _parseDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value);
  }
  return null;
}
