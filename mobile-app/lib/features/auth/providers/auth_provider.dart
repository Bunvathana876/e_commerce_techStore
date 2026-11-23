import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/network/api_client.dart';
import '../models/user_model.dart';
import '../services/auth_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService;

  // Storage keys
  static const String _keyToken = 'auth_token';
  static const String _keyUser = 'auth_user';

  // Coordinated logout listeners across providers
  static final List<FutureOr<void> Function()> _logoutListeners = [];
  // Coordinated login listeners across providers (e.g. remote cart restore)
  static final List<FutureOr<void> Function()> _loginListeners = [];

  static void registerLogoutListener(FutureOr<void> Function() listener) {
    if (!_logoutListeners.contains(listener)) {
      _logoutListeners.add(listener);
    }
  }

  static void unregisterLogoutListener(FutureOr<void> Function() listener) {
    _logoutListeners.remove(listener);
  }

  static void clearLogoutListeners() {
    _logoutListeners.clear();
  }

  static void registerLoginListener(FutureOr<void> Function() listener) {
    if (!_loginListeners.contains(listener)) {
      _loginListeners.add(listener);
    }
  }

  static void unregisterLoginListener(FutureOr<void> Function() listener) {
    _loginListeners.remove(listener);
  }

  static void clearLoginListeners() {
    _loginListeners.clear();
  }

  Future<void> _notifyLoginListeners() async {
    final listeners = List<FutureOr<void> Function()>.from(_loginListeners);
    for (final listener in listeners) {
      try {
        await listener();
      } catch (e) {
        debugPrint('Login listener failed: $e');
      }
    }
  }

  AuthProvider({AuthService? authService, SharedPreferences? initialPrefs})
    : _authService = authService ?? AuthService() {
    // Intercept 401 Unauthorized responses to perform clean automatic logout
    ApiClient.globalOnUnauthorized = () {
      unawaited(logout());
    };
    ApiClient.instance.onUnauthorized = () {
      unawaited(logout());
    };

    if (initialPrefs != null) {
      _loadFromPrefs(initialPrefs);
    } else {
      _loadSavedSession();
    }
  }

  UserModel? _currentUser;
  String? _token;
  bool _isLoading = false;
  bool _isInitialized = false;
  String? _errorMessage;
  int _sessionEpoch = 0;
  bool _isLoggingOut = false;

  UserModel? get currentUser => _currentUser;
  String? get token => _token;
  bool get isLoading => _isLoading;
  bool get isInitialized => _isInitialized;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _token != null && _currentUser != null;
  int get sessionEpoch => _sessionEpoch;

  // Instance convenience to register cleanup listeners
  void registerSessionCleanup(FutureOr<void> Function() callback) {
    registerLogoutListener(callback);
  }

  // Restore session from SharedPreferences
  void _loadFromPrefs(SharedPreferences prefs) {
    try {
      final savedToken = prefs.getString(_keyToken);
      final savedUserJson = prefs.getString(_keyUser);

      if (savedToken != null &&
          savedToken.isNotEmpty &&
          savedUserJson != null &&
          savedUserJson.isNotEmpty) {
        final Map<String, dynamic> userMap =
            jsonDecode(savedUserJson) as Map<String, dynamic>;
        _token = savedToken;
        _currentUser = UserModel.fromJson(userMap);
        ApiClient.instance.setAuthToken(savedToken);
      } else {
        _token = null;
        _currentUser = null;
        ApiClient.instance.clearAuthToken();
      }
    } catch (_) {
      debugPrint('Failed to restore saved session.');
      _token = null;
      _currentUser = null;
      ApiClient.instance.clearAuthToken();
    } finally {
      _isInitialized = true;
    }
  }

  // Load saved session from storage
  Future<void> _loadSavedSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _loadFromPrefs(prefs);
    } catch (_) {
      debugPrint('Failed to initialize SharedPreferences.');
      _isInitialized = true;
    }
    notifyListeners();
  }

  // Centralized session cleanup helper: wipes SharedPreferences & invokes provider listeners
  Future<void> _clearSessionData(SharedPreferences prefs) async {
    // Clean known session-specific storage keys
    await prefs.remove(_keyToken);
    await prefs.remove(_keyUser);
    await prefs.remove('user_orders_cache');
    await prefs.remove('notifications_has_cleared');
    await prefs.remove('notifications_deleted_ids');

    // Remove any user-scoped or dynamic cache keys (preserving app_theme_mode)
    final keys = prefs.getKeys();
    for (final key in keys) {
      if (key.startsWith('user_orders_cache') ||
          key.startsWith('notifications_')) {
        await prefs.remove(key);
      }
    }

    // Trigger all registered logout / session isolation callbacks
    final listeners = List<FutureOr<void> Function()>.from(_logoutListeners);
    for (final listener in listeners) {
      try {
        await listener();
      } catch (_) {
        debugPrint('Session cleanup listener failed.');
      }
    }
  }

  // Sign in and save session
  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _authService.login(
        email: email,
        password: password,
      );
      final resolvedToken =
          (response['token'] ?? response['access_token'])?.toString().trim() ??
          '';
      final rawUser = response['user'];
      if (resolvedToken.isEmpty || rawUser is! Map) {
        throw Exception('Invalid authentication response from server.');
      }

      // Wipe previous session artifacts before activating new user
      _sessionEpoch++;
      final prefs = await SharedPreferences.getInstance();
      await _clearSessionData(prefs);

      _token = resolvedToken;
      _currentUser = UserModel.fromJson(Map<String, dynamic>.from(rawUser));
      ApiClient.instance.setAuthToken(_token!);

      // Persist login session to local storage
      await prefs.setString(_keyToken, _token!);
      await prefs.setString(_keyUser, jsonEncode(_currentUser!.toJson()));

      _isLoading = false;
      notifyListeners();
      unawaited(_notifyLoginListeners());
      return true;
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString().replaceFirst('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  // Register new account and save session
  Future<bool> signUp({
    required String fullName,
    required String email,
    required String password,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _authService.signUp(
        fullName: fullName,
        email: email,
        password: password,
      );
      final resolvedToken =
          (response['token'] ?? response['access_token'])?.toString().trim() ??
          '';
      final rawUser = response['user'];
      if (resolvedToken.isEmpty || rawUser is! Map) {
        throw Exception('Invalid registration response from server.');
      }

      // Wipe previous session artifacts before activating new user
      _sessionEpoch++;
      final prefs = await SharedPreferences.getInstance();
      await _clearSessionData(prefs);

      _token = resolvedToken;
      _currentUser = UserModel.fromJson(Map<String, dynamic>.from(rawUser));
      ApiClient.instance.setAuthToken(_token!);

      await prefs.setString(_keyToken, _token!);
      await prefs.setString(_keyUser, jsonEncode(_currentUser!.toJson()));

      _isLoading = false;
      notifyListeners();
      unawaited(_notifyLoginListeners());
      return true;
    } catch (e) {
      _isLoading = false;
      _errorMessage = e.toString().replaceFirst('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  // Update and save user session directly
  Future<void> saveUserSession({
    required String token,
    required UserModel user,
  }) async {
    _sessionEpoch++;
    _token = token;
    _currentUser = user;
    ApiClient.instance.setAuthToken(token);

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_keyToken, token);
      await prefs.setString(_keyUser, jsonEncode(user.toJson()));
    } catch (_) {
      debugPrint('Failed to save user session.');
    }

    notifyListeners();
    unawaited(_notifyLoginListeners());
  }

  // Log out and clear stored session
  Future<void> logout() async {
    if (_isLoggingOut) return;
    _isLoggingOut = true;
    // Capture and dispatch before clearing the shared bearer. Attach the failure
    // handler immediately; no remote completion may mutate a later login.
    final remoteLogout = _token == null
        ? Future<void>.value()
        : _authService.logout(token: _token).catchError((Object _) {});

    try {
      _sessionEpoch++;
      _currentUser = null;
      _token = null;
      _errorMessage = null;
      ApiClient.instance.clearAuthToken();

      try {
        final prefs = await SharedPreferences.getInstance();
        await _clearSessionData(prefs);
      } catch (_) {
        debugPrint('Failed to clear saved session.');
      }

      notifyListeners();
    } finally {
      _isLoggingOut = false;
    }
    await remoteLogout;
  }

  // Request a single-use password reset email via backend SMTP / SendGrid
  Future<Map<String, dynamic>?> requestPasswordReset(String email) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final result = await _authService.requestPasswordReset(email);
      _isLoading = false;
      notifyListeners();
      return result;
    } catch (e) {
      _isLoading = false;
      _errorMessage = e
          .toString()
          .replaceFirst('Exception: ', '')
          .replaceFirst('ApiException: ', '');
      notifyListeners();
      return null;
    }
  }

  // Validate a reset token before submitting password update
  Future<bool> validateResetToken(String token) async {
    try {
      return await _authService.validateResetToken(token);
    } catch (_) {
      return false;
    }
  }

  // Confirm password reset using issued token and new password
  Future<bool> confirmPasswordReset({
    required String token,
    required String newPassword,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _authService.confirmPasswordReset(
        token: token,
        newPassword: newPassword,
      );
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _isLoading = false;
      _errorMessage = e
          .toString()
          .replaceFirst('Exception: ', '')
          .replaceFirst('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }
}
