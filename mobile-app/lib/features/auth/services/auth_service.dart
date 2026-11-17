import 'dart:async';
import 'auth_api_service.dart';

// Authentication service supporting both REST backend and mock mode
class AuthService {
  final AuthApiService _apiService;
  final bool useRemoteBackend;

  AuthService({AuthApiService? apiService, this.useRemoteBackend = true})
    : _apiService = apiService ?? AuthApiService();

  // Sign in via remote API; explicit mock mode requires useRemoteBackend: false
  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    if (useRemoteBackend) {
      return await _apiService.login(email: email, password: password);
    }

    // Simulate network latency for explicit offline demo/test mode only
    await Future.delayed(const Duration(milliseconds: 600));

    if (email == 'student@example.com' && password == 'password123') {
      return _mockStudentSession();
    } else {
      throw Exception(
        'Invalid email or password. Use student@example.com / password123',
      );
    }
  }

  Map<String, dynamic> _mockStudentSession() {
    return {
      'token': 'mock_jwt_access_token_xyz',
      'access_token': 'mock_jwt_access_token_xyz',
      'user': {
        'id': 1,
        'email': 'student@example.com',
        'full_name': 'Bun Vathana',
        'name': 'Bun Vathana',
        'role': 'customer',
        'avatar_url': null,
      },
    };
  }

  // Register new account via remote API; explicit mock mode requires useRemoteBackend: false
  Future<Map<String, dynamic>> signUp({
    required String fullName,
    required String email,
    required String password,
  }) async {
    if (useRemoteBackend) {
      return await _apiService.signUp(
        fullName: fullName,
        email: email,
        password: password,
      );
    }

    await Future.delayed(const Duration(milliseconds: 600));
    return _mockRegisteredSession(fullName, email);
  }

  // Safely end session on backend
  Future<void> logout({String? token}) async {
    if (useRemoteBackend) {
      await _apiService.logout(token: token);
    }
  }

  Map<String, dynamic> _mockRegisteredSession(String fullName, String email) {
    return {
      'token': 'mock_jwt_access_token_registered',
      'access_token': 'mock_jwt_access_token_registered',
      'user': {
        'id': 2,
        'email': email,
        'full_name': fullName,
        'name': fullName,
        'role': 'customer',
        'avatar_url': null,
      },
    };
  }
}
