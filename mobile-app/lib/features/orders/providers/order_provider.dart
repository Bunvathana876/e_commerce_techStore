import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/order_model.dart';
import '../services/order_api_service.dart';

/// State management provider for customer orders.
/// Supports backend synchronization, local session persistence via SharedPreferences,
/// and truthful status handling with zero fabricated records.
class OrderProvider extends ChangeNotifier {
  final OrderApiService _apiService;
  SharedPreferences? _prefs;

  static const String _ordersStorageKey = 'user_orders_cache';

  List<OrderModel> _orders = [];
  bool _isLoading = false;
  String? _errorMessage;
  bool _isInitialized = false;
  int _sessionEpoch = 0;

  OrderProvider({OrderApiService? apiService, SharedPreferences? initialPrefs})
    : _apiService = apiService ?? OrderApiService(),
      _prefs = initialPrefs {
    AuthProvider.registerLogoutListener(clearOrders);
    if (initialPrefs != null) {
      _loadOrdersFromStorage(initialPrefs);
    } else {
      _initPrefsAndLoad();
    }
  }

  List<OrderModel> get orders => List.unmodifiable(_orders);
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isInitialized => _isInitialized;
  int get sessionEpoch => _sessionEpoch;

  /// Returns count of active (in-progress) orders: pending, processing, shipped
  int get activeOrdersCount => _orders.where((o) => o.isActive).length;

  /// Total count of all orders placed
  int get totalOrdersCount => _orders.length;

  /// Finds an order by its ID
  OrderModel? getOrderById(int orderId) {
    try {
      return _orders.firstWhere((o) => o.id == orderId);
    } catch (_) {
      return null;
    }
  }

  Future<void> _initPrefsAndLoad() async {
    try {
      _prefs = await SharedPreferences.getInstance();
      if (_prefs != null) {
        _loadOrdersFromStorage(_prefs!);
      }
    } catch (e) {
      debugPrint('OrderProvider prefs initialization notice: $e');
    } finally {
      _isInitialized = true;
      notifyListeners();
    }
  }

  void _loadOrdersFromStorage(SharedPreferences prefs) {
    try {
      final jsonStr = prefs.getString(_ordersStorageKey);
      if (jsonStr != null && jsonStr.isNotEmpty) {
        final decoded = jsonDecode(jsonStr);
        if (decoded is List) {
          _orders = decoded
              .whereType<Map<String, dynamic>>()
              .map((item) => OrderModel.fromJson(item))
              .where((order) => order.id > 0)
              .toList();
        }
      }
    } catch (e) {
      debugPrint('Error loading cached orders: $e');
    } finally {
      _isInitialized = true;
    }
  }

  Future<void> _saveOrdersToStorage() async {
    if (_prefs == null) return;
    try {
      final jsonList = _orders.map((o) => o.toJson()).toList();
      await _prefs!.setString(_ordersStorageKey, jsonEncode(jsonList));
    } catch (e) {
      debugPrint('Error saving orders to cache: $e');
    }
  }

  /// Syncs order records from the backend API if authenticated
  Future<void> fetchOrders({bool forceRefresh = false}) async {
    if (_isLoading) return;
    final requestEpoch = _sessionEpoch;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_apiService.client.isAuthenticated) {
        final remoteOrders = await _apiService.getOrders();
        if (requestEpoch != _sessionEpoch || !_apiService.client.isAuthenticated) {
          return;
        }

        // Replace with authoritative server-confirmed orders (deduplicating by ID)
        final existingIds = <int>{};
        final synced = <OrderModel>[];

        for (final order in remoteOrders) {
          if (order.id > 0 && !existingIds.contains(order.id)) {
            existingIds.add(order.id);
            synced.add(order);
          }
        }

        // Sort descending by creation date
        synced.sort((a, b) => b.createdAt.compareTo(a.createdAt));
        _orders = synced;
        await _saveOrdersToStorage();
      }
    } catch (e) {
      if (requestEpoch == _sessionEpoch) {
        _errorMessage = 'Could not sync latest orders: $e';
        debugPrint(_errorMessage);
      }
    } finally {
      if (requestEpoch == _sessionEpoch) {
        _isLoading = false;
        notifyListeners();
      }
    }
  }

  /// Records a server-confirmed order into local cache and state immediately
  void recordOrder(OrderModel order) {
    if (order.id <= 0) return;
    // Insert at front
    _orders.removeWhere((o) => o.id == order.id);
    _orders.insert(0, order);
    _saveOrdersToStorage();
    notifyListeners();
  }

  /// Clears stored order cache (e.g. on logout)
  Future<void> clearOrders() async {
    _sessionEpoch++;
    _orders = [];
    _errorMessage = null;
    if (_prefs != null) {
      await _prefs!.remove(_ordersStorageKey);
      final keys = _prefs!.getKeys();
      for (final key in keys) {
        if (key.startsWith('user_orders_cache')) {
          await _prefs!.remove(key);
        }
      }
    }
    notifyListeners();
  }

  @override
  void dispose() {
    AuthProvider.unregisterLogoutListener(clearOrders);
    super.dispose();
  }
}
