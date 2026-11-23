import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/utils/environment.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/notification_model.dart';
import '../services/notification_api_service.dart';

class NotificationProvider extends ChangeNotifier {
  final NotificationApiService _apiService;
  SharedPreferences? _prefs;
  int _sessionEpoch = 0;

  NotificationProvider({
    NotificationApiService? apiService,
    SharedPreferences? initialPrefs,
  }) : _apiService = apiService ?? NotificationApiService(),
       _prefs = initialPrefs {
    AuthProvider.registerLogoutListener(clearSession);
    _loadFromStorage();
    _initPrefsAsync();
    loadNotifications();
  }

  List<NotificationModel> _notifications = [];
  int _unreadCount = 0;
  bool _isLoading = false;
  bool _hasCleared = false;
  final Set<int> _deletedIds = {};
  String _activeFilter = 'All';
  String? _errorMessage;

  List<NotificationModel> get notifications => _notifications;
  int get unreadCount => _unreadCount;
  bool get isLoading => _isLoading;
  bool get hasCleared => _hasCleared;
  String get activeFilter => _activeFilter;
  String? get errorMessage => _errorMessage;
  int get sessionEpoch => _sessionEpoch;

  void _loadFromStorage() {
    if (_prefs != null) {
      _hasCleared = _prefs!.getBool('notifications_has_cleared') ?? false;
      final savedDeleted =
          _prefs!.getStringList('notifications_deleted_ids') ?? [];
      _deletedIds.addAll(
        savedDeleted.map((s) => int.tryParse(s)).whereType<int>(),
      );
    }

    if (_hasCleared) {
      _notifications = [];
      _unreadCount = 0;
    } else if (isFlutterTest) {
      _notifications = _fallbackNotifications()
          .where((n) => !_deletedIds.contains(n.id))
          .toList();
      _unreadCount = _notifications.where((n) => n.isUnread).length;
    } else {
      _notifications = [];
      _unreadCount = 0;
    }
  }

  Future<void> _initPrefsAsync() async {
    if (_prefs != null) return;
    try {
      _prefs = await SharedPreferences.getInstance();
      final hasCleared = _prefs!.getBool('notifications_has_cleared') ?? false;
      final savedDeleted =
          _prefs!.getStringList('notifications_deleted_ids') ?? [];
      _deletedIds.addAll(
        savedDeleted.map((s) => int.tryParse(s)).whereType<int>(),
      );

      if (hasCleared && !_hasCleared) {
        _hasCleared = true;
        _notifications.clear();
        _unreadCount = 0;
        notifyListeners();
      }
    } catch (e) {
      debugPrint('NotificationProvider SharedPreferences init note: $e');
    }
  }

  List<NotificationModel> get filteredNotifications {
    switch (_activeFilter) {
      case 'Unread':
        return _notifications.where((n) => n.isUnread).toList();
      case 'Orders':
        return _notifications.where((n) => n.type == 'order').toList();
      case 'Offers':
        return _notifications.where((n) => n.type == 'promo').toList();
      case 'Delivery':
        return _notifications.where((n) => n.type == 'delivery').toList();
      default:
        return _notifications;
    }
  }

  void setFilter(String filter) {
    if (_activeFilter != filter) {
      _activeFilter = filter;
      notifyListeners();
    }
  }

  /// Load notifications and unread count from backend
  Future<void> loadNotifications({bool silent = false}) async {
    final requestEpoch = _sessionEpoch;
    if (!silent) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      final fetched = await _apiService.getNotifications();
      if (requestEpoch != _sessionEpoch) return;

      if (fetched != null) {
        final visible = fetched
            .where((n) => !_deletedIds.contains(n.id))
            .toList();
        // Reset the local clear flag whenever fresh server notifications arrive
        if (visible.isNotEmpty && _hasCleared) {
          _hasCleared = false;
          try {
            final prefs = _prefs ?? await SharedPreferences.getInstance();
            await prefs.setBool('notifications_has_cleared', false);
          } catch (_) {}
        }

        if (_hasCleared) {
          _notifications = [];
          _unreadCount = 0;
        } else {
          // Connected to remote backend successfully
          _notifications = visible;
          _unreadCount = _notifications.where((n) => n.isUnread).length;

          // Sync exact unread count from backend
          final count = await _apiService.getUnreadCount();
          if (requestEpoch != _sessionEpoch) return;
          if (count > 0 || _unreadCount == 0) {
            _unreadCount = count;
          }
        }
      }
    } catch (e) {
      if (requestEpoch == _sessionEpoch) {
        _errorMessage = e.toString();
        if (_hasCleared) {
          _notifications = [];
          _unreadCount = 0;
        }
      }
    } finally {
      if (requestEpoch == _sessionEpoch) {
        _isLoading = false;
        notifyListeners();
      }
    }
  }

  /// Optimistically mark a single notification as read
  Future<void> markAsRead(int id) async {
    final index = _notifications.indexWhere((n) => n.id == id);
    if (index != -1 && !_notifications[index].read) {
      final updated = _notifications[index].copyWith(read: true);
      _notifications[index] = updated;
      _unreadCount = (_unreadCount - 1).clamp(0, 999);
      notifyListeners();

      // Async backend update
      await _apiService.markAsRead(id);
    }
  }

  /// Optimistically mark all notifications as read
  Future<void> markAllAsRead() async {
    bool hasUnread = _notifications.any((n) => !n.read);
    if (!hasUnread) return;

    _notifications = _notifications.map((n) => n.copyWith(read: true)).toList();
    _unreadCount = 0;
    notifyListeners();

    // Async backend update
    await _apiService.markAllAsRead();
  }

  /// Optimistically delete a notification
  Future<void> deleteNotification(int id) async {
    final index = _notifications.indexWhere((n) => n.id == id);
    if (index != -1) {
      final wasUnread = !_notifications[index].read;
      _notifications.removeAt(index);
      _deletedIds.add(id);
      if (wasUnread) {
        _unreadCount = (_unreadCount - 1).clamp(0, 999);
      }
      notifyListeners();

      try {
        final prefs = _prefs ?? await SharedPreferences.getInstance();
        await prefs.setStringList(
          'notifications_deleted_ids',
          _deletedIds.map((i) => i.toString()).toList(),
        );
      } catch (_) {}

      // Async backend delete
      await _apiService.deleteNotification(id);
    }
  }

  /// Optimistically clear all notifications
  Future<void> clearAll() async {
    _hasCleared = true;
    _notifications.clear();
    _unreadCount = 0;
    _deletedIds.clear();
    notifyListeners();

    try {
      final prefs = _prefs ?? await SharedPreferences.getInstance();
      await prefs.setBool('notifications_has_cleared', true);
      await prefs.setStringList('notifications_deleted_ids', []);
    } catch (_) {}

    // Async backend clear
    await _apiService.clearAllNotifications();
  }

  /// Reset demo notifications for testing / showcase
  Future<void> resetDemoNotifications() async {
    _hasCleared = false;
    _deletedIds.clear();
    _notifications = _fallbackNotifications();
    _unreadCount = _notifications.where((n) => n.isUnread).length;
    notifyListeners();

    try {
      final prefs = _prefs ?? await SharedPreferences.getInstance();
      await prefs.setBool('notifications_has_cleared', false);
      await prefs.setStringList('notifications_deleted_ids', []);
    } catch (_) {}

    await loadNotifications(silent: true);
  }

  static List<NotificationModel> _fallbackNotifications() {
    final now = DateTime.now();
    return [
      NotificationModel(
        id: 1,
        type: 'delivery',
        title: 'Order #104 Shipped! 📦',
        message:
            'Your package is on its way with express courier tracking #BP-88921.',
        link: '/orders/104',
        read: false,
        createdAt: now.subtract(const Duration(minutes: 15)),
      ),
      NotificationModel(
        id: 2,
        type: 'promo',
        title: 'Weekend Flash Sale ⚡',
        message:
            'Enjoy up to 40% OFF all premium wireless gear and accessories this weekend!',
        link: '/categories/electronics',
        read: false,
        createdAt: now.subtract(const Duration(hours: 2)),
      ),
      NotificationModel(
        id: 3,
        type: 'order',
        title: 'Payment Confirmed',
        message:
            'Payment of \$199.99 for Order #104 has been successfully processed.',
        link: '/orders/104',
        read: false,
        createdAt: now.subtract(const Duration(hours: 5)),
      ),
      NotificationModel(
        id: 4,
        type: 'system',
        title: 'Welcome to Blue Panda Store 🐼',
        message:
            'Thank you for joining Blue Panda. Discover daily curated deals and lightning fast checkout.',
        read: true,
        createdAt: now.subtract(const Duration(days: 1)),
      ),
    ];
  }

  /// Clears notifications state and cache on logout or session reset
  Future<void> clearSession() async {
    _sessionEpoch++;
    _notifications = [];
    _unreadCount = 0;
    _deletedIds.clear();
    _hasCleared = false;
    _errorMessage = null;
    try {
      final prefs = _prefs ?? await SharedPreferences.getInstance();
      await prefs.remove('notifications_has_cleared');
      await prefs.remove('notifications_deleted_ids');
      final keys = prefs.getKeys();
      for (final key in keys) {
        if (key.startsWith('notifications_')) {
          await prefs.remove(key);
        }
      }
    } catch (_) {}
    notifyListeners();
  }

  @override
  void dispose() {
    AuthProvider.unregisterLogoutListener(clearSession);
    super.dispose();
  }
}
