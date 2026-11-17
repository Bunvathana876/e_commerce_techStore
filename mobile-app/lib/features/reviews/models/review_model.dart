import '../../../core/constants/api_endpoints.dart';

/// Review model representing customer reviews and ratings from backend PostgreSQL
class ReviewModel {
  final int id;
  final int productId;
  final int userId;
  final int? orderId;
  final int rating;
  final String comment;
  final String status;
  final String? adminReply;
  final DateTime? adminRepliedAt;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final String userName;
  final String? userAvatar;
  final String? userEmail;

  const ReviewModel({
    required this.id,
    required this.productId,
    required this.userId,
    this.orderId,
    required this.rating,
    required this.comment,
    required this.status,
    this.adminReply,
    this.adminRepliedAt,
    required this.createdAt,
    this.updatedAt,
    required this.userName,
    this.userAvatar,
    this.userEmail,
  });

  /// Check if review is publicly visible / approved
  bool get isApproved => status.toLowerCase() == 'approved';

  /// Relative formatted time (e.g. "2d ago", "Sep 27, 2026")
  String get formattedDate {
    final now = DateTime.now();
    final difference = now.difference(createdAt);

    if (difference.inDays == 0) {
      if (difference.inHours == 0) {
        if (difference.inMinutes <= 1) {
          return 'Just now';
        }
        return '${difference.inMinutes}m ago';
      }
      return '${difference.inHours}h ago';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}d ago';
    } else {
      final months = [
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
      final month = months[createdAt.month - 1];
      return '$month ${createdAt.day}, ${createdAt.year}';
    }
  }

  /// User initials for avatar fallback (e.g. "L" or "JD")
  String get userInitials {
    final trimmed = userName.trim();
    if (trimmed.isEmpty) return 'U';
    final parts = trimmed.split(' ').where((p) => p.isNotEmpty).toList();
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    return trimmed[0].toUpperCase();
  }

  factory ReviewModel.fromJson(Map<String, dynamic> json) {
    // Parse user object if present
    String uName = 'Customer';
    String? uAvatar;
    String? uEmail;

    if (json['user'] is Map<String, dynamic>) {
      final userMap = json['user'] as Map<String, dynamic>;
      uName = userMap['name'] as String? ?? 'Customer';
      final rawAvatar = userMap['avatar'] as String?;
      if (rawAvatar != null && rawAvatar.isNotEmpty) {
        uAvatar = ApiEndpoints.normalizeImageUrl(rawAvatar);
      }
      uEmail = userMap['email'] as String?;
    } else if (json['user_name'] != null) {
      uName = json['user_name'] as String;
    }

    DateTime created;
    try {
      created = json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : DateTime.now();
    } catch (_) {
      created = DateTime.now();
    }

    DateTime? adminReplied;
    if (json['admin_replied_at'] != null) {
      try {
        adminReplied = DateTime.parse(json['admin_replied_at'] as String);
      } catch (_) {}
    }

    DateTime? updated;
    if (json['updated_at'] != null) {
      try {
        updated = DateTime.parse(json['updated_at'] as String);
      } catch (_) {}
    }

    return ReviewModel(
      id: (json['id'] as num?)?.toInt() ?? 0,
      productId: (json['product_id'] as num?)?.toInt() ?? 0,
      userId: (json['user_id'] as num?)?.toInt() ?? 0,
      orderId: (json['order_id'] as num?)?.toInt(),
      rating: (json['rating'] as num?)?.toInt() ?? 5,
      comment: json['comment'] as String? ?? '',
      status: json['status'] as String? ?? 'approved',
      adminReply: json['admin_reply'] as String?,
      adminRepliedAt: adminReplied,
      createdAt: created,
      updatedAt: updated,
      userName: uName,
      userAvatar: uAvatar,
      userEmail: uEmail,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'product_id': productId,
      'user_id': userId,
      'order_id': orderId,
      'rating': rating,
      'comment': comment,
      'status': status,
      'admin_reply': adminReply,
      'admin_replied_at': adminRepliedAt?.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
      'user': {
        'id': userId,
        'name': userName,
        'email': userEmail,
        'avatar': userAvatar,
      },
    };
  }
}
