import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../models/address_model.dart';

class AddressService {
  final ApiClient client;
  AddressService({ApiClient? client}) : client = client ?? ApiClient.instance;

  Future<int> currentUserId() async {
    final response = await client.get<int>(
      ApiEndpoints.me,
      parser: (data) => (data['id'] as num).toInt(),
    );
    if (!response.success || response.data == null || response.data! <= 0) {
      throw const ApiException(
        'Could not verify your account. Please sign in again.',
      );
    }
    return response.data!;
  }

  Future<List<AddressModel>> list(int userId) async {
    final response = await client.get<List<AddressModel>>(
      ApiEndpoints.addresses,
      parser: (data) =>
          (data as List).map((item) => _parse(item, userId)).toList(),
    );
    if (!response.success || response.data == null) {
      throw const ApiException('Could not load your delivery addresses.');
    }
    return response.data!;
  }

  Future<AddressModel> create(int userId, Map<String, dynamic> address) async {
    final response = await client.post<AddressModel>(
      ApiEndpoints.addresses,
      body: address,
      parser: (data) => _parse(data, userId),
    );
    if (!response.success || response.data == null) {
      throw const ApiException('Could not save your delivery address.');
    }
    return response.data!;
  }

  AddressModel _parse(dynamic data, int userId) {
    if (data is! Map<String, dynamic> || data['user_id'] != userId) {
      throw const ApiException('Could not verify address ownership.');
    }
    final address = AddressModel.fromJson(data);
    if (address.id <= 0 ||
        address.streetAddress.trim().isEmpty ||
        address.city.trim().isEmpty ||
        address.recipientName.trim().isEmpty ||
        address.phoneNumber.trim().isEmpty) {
      throw const ApiException(
        'This address is incomplete. Please add a complete address.',
      );
    }
    return address;
  }
}
