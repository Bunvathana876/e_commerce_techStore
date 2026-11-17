import 'package:flutter/material.dart';

class NotificationModel {
  final int id;
  final int? userId;
  final String type;
  final String title;
  final String message;
  final String? link;
  final bool read;
  final DateTime createdAt;
  final DateTime? updatedAt;

  const NotificationModel({
    required this.id,
    this.userId,
    required this.type,
    required this.title,
    required this.message,
    this.link,
    this.read = false,
    required this.createdAt,
    this.updatedAt,
  });

  bool get isUnread => !read;

  NotificationModel copyWith({
    int? id,
    int? userId,
    String? type,
    String? title,
    String? message,
    String? link,
    bool? read,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return NotificationModel(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      type: type ?? this.type,
      title: title ?? this.title,
      message: message ?? this.message,
      link: link ?? this.link,
      read: read ?? this.read,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    DateTime parseDate(dynamic val) {
      if (val is String && val.isNotEmpty) {
        try {
          return DateTime.parse(val);
        } catch (_) {
          return DateTime.now();
        }
      }
      return DateTime.now();
    }

    return NotificationModel(
      id: json['id'] is int
          ? json['id'] as int
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      userId: json['user_id'] is int
          ? json['user_id'] as int
          : (json['user_id'] != null
                ? int.tryParse(json['user_id'].toString())
                : null),
      type: (json['type']?.toString() ?? 'system').toLowerCase(),
      title: json['title']?.toString() ?? '',
      message: json['message']?.toString() ?? '',
      link: json['link']?.toString(),
      read: json['read'] == true,
      createdAt: parseDate(json['created_at']),
      updatedAt: json['updated_at'] != null
          ? parseDate(json['updated_at'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'type': type,
      'title': title,
      'message': message,
      'link': link,
      'read': read,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  /// Relative human-readable time
  String get formattedTime {
    final now = DateTime.now();
    final difference = now.difference(createdAt);

    if (difference.inSeconds < 45) {
      return 'Just now';
    } else if (difference.inMinutes < 60) {
      final m = difference.inMinutes;
      return '${m <= 0 ? 1 : m}m ago';
    } else if (difference.inHours < 24) {
      final h = difference.inHours;
      return '${h}h ago';
    } else if (difference.inDays == 1) {
      return 'Yesterday';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}d ago';
    } else if (difference.inDays < 30) {
      final w = (difference.inDays / 7).floor();
      return '$w ${w == 1 ? 'week' : 'weeks'} ago';
    } else {
      return '${createdAt.day}/${createdAt.month}/${createdAt.year}';
    }
  }

  /// Category Icon
  IconData get iconData {
    switch (type) {
      case 'delivery':
        return Icons.local_shipping_rounded;
      case 'order':
        return Icons.shopping_bag_rounded;
      case 'promo':
        return Icons.local_offer_rounded;
      case 'review':
        return Icons.star_rounded;
      case 'stock':
        return Icons.inventory_2_rounded;
      case 'payment':
        return Icons.credit_card_rounded;
      default:
        return Icons.notifications_rounded;
    }
  }

  /// Primary Accent Color
  Color get accentColor {
    switch (type) {
      case 'delivery':
        return const Color(0xFF10B981); // Emerald
      case 'order':
        return const Color(0xFF2563EB); // Blue
      case 'promo':
        return const Color(0xFF8B5CF6); // Purple
      case 'review':
        return const Color(0xFFF59E0B); // Amber
      case 'stock':
        return const Color(0xFFEF4444); // Red
      case 'payment':
        return const Color(0xFF059669); // Dark green
      default:
        return const Color(0xFF64748B); // Slate
    }
  }

  /// Category display badge label
  String get typeLabel {
    switch (type) {
      case 'delivery':
        return 'Delivery';
      case 'order':
        return 'Order';
      case 'promo':
        return 'Promotion';
      case 'review':
        return 'Review';
      case 'stock':
        return 'Stock';
      case 'payment':
        return 'Payment';
      default:
        return 'System';
    }
  }
}
