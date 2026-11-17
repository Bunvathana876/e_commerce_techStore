import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/notification_model.dart';

/// Service connecting to the backend notifications API endpoints
class NotificationApiService {
  final ApiClient _client;

  NotificationApiService({ApiClient? client})
    : _client = client ?? ApiClient.instance;

  /// Fetch notifications with optional type and unread filters
  Future<List<NotificationModel>?> getNotifications({
    String? type,
    bool unreadOnly = false,
  }) async {
    try {
      final query = <String, dynamic>{};
      if (type != null && type.isNotEmpty && type.toLowerCase() != 'all') {
        query['type'] = type.toLowerCase();
      }
      if (unreadOnly) {
        query['unread_only'] = true;
      }

      final response = await _client.get<List<NotificationModel>>(
        ApiEndpoints.notifications,
        queryParameters: query.isNotEmpty ? query : null,
        parser: (data) => _parseNotificationList(data),
      );

      return response.data ?? [];
    } catch (_) {
      // In case the network is temporarily offline or unreachable, return null
      return null;
    }
  }

  /// Get real-time unread notification count
  Future<int> getUnreadCount() async {
    try {
      final response = await _client.get<int>(
        ApiEndpoints.notificationsUnreadCount,
        parser: (data) {
          if (data is Map<String, dynamic>) {
            return (data['unread_count'] is int)
                ? data['unread_count'] as int
                : int.tryParse(data['unread_count']?.toString() ?? '0') ?? 0;
          }
          return 0;
        },
      );
      return response.data ?? 0;
    } catch (_) {
      return 0;
    }
  }

  /// Mark single notification as read
  Future<bool> markAsRead(int id) async {
    try {
      final response = await _client.patch<bool>(
        ApiEndpoints.notificationRead(id),
        parser: (data) => true,
      );
      return response.success;
    } catch (_) {
      return false;
    }
  }

  /// Mark all notifications as read
  Future<bool> markAllAsRead() async {
    try {
      final response = await _client.post<bool>(
        ApiEndpoints.notificationsReadAll,
        parser: (data) => true,
      );
      return response.success;
    } catch (_) {
      return false;
    }
  }

  /// Delete a notification
  Future<bool> deleteNotification(int id) async {
    try {
      final response = await _client.delete<bool>(
        ApiEndpoints.notificationDelete(id),
        parser: (data) => true,
      );
      return response.success;
    } catch (_) {
      return false;
    }
  }

  /// Clear all notifications
  Future<bool> clearAllNotifications() async {
    try {
      final response = await _client.delete<bool>(
        ApiEndpoints.notifications,
        parser: (data) => true,
      );
      return response.success;
    } catch (_) {
      return false;
    }
  }

  List<NotificationModel> _parseNotificationList(dynamic data) {
    if (data is List) {
      return data
          .map(
            (item) => NotificationModel.fromJson(item as Map<String, dynamic>),
          )
          .toList();
    }
    return [];
  }
}
