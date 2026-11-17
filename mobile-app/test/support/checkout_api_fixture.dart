import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> checkoutAddress({int id = 1, int userId = 7}) => {
  'id': id,
  'user_id': userId,
  'full_name': id == 1 ? 'Test Customer' : 'Second Recipient',
  'phone': '012345678',
  'address_line': 'Test street $id',
  'city': 'Test City',
  'province': 'Test Province',
  'postal_code': '12000',
  'is_default': id == 1,
};

MockClient checkoutClient(
  FutureOr<http.Response> Function(http.Request) handler,
) => MockClient((request) async {
  if (request.method == 'GET' && request.url.path.endsWith('/auth/me')) {
    return http.Response(
      jsonEncode({
        'success': true,
        'data': {'id': 7},
      }),
      200,
    );
  }
  if (request.method == 'GET' && request.url.path.endsWith('/addresses')) {
    return http.Response(
      jsonEncode({
        'success': true,
        'data': [checkoutAddress(), checkoutAddress(id: 2)],
      }),
      200,
    );
  }
  return handler(request);
});
