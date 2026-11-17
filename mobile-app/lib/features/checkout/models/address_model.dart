class AddressModel {
  final int id;
  final String label; // e.g. "Home", "Office"
  final String recipientName;
  final String phoneNumber;
  final String streetAddress;
  final String city;
  final bool isDefault;
  final String? province;
  final String? postalCode;

  const AddressModel({
    required this.id,
    required this.label,
    required this.recipientName,
    required this.phoneNumber,
    required this.streetAddress,
    required this.city,
    this.isDefault = false,
    this.province,
    this.postalCode,
  });

  factory AddressModel.fromJson(Map<String, dynamic> json) => AddressModel(
    id: (json['id'] as num).toInt(),
    label: json['is_default'] == true ? 'Default address' : 'Delivery address',
    recipientName: json['full_name'] as String,
    phoneNumber: json['phone'] as String,
    streetAddress: json['address_line'] as String,
    city: json['city'] as String,
    province: json['province'] as String?,
    postalCode: json['postal_code'] as String?,
    isDefault: json['is_default'] == true,
  );

  String get fullAddress => [
    recipientName,
    phoneNumber,
    streetAddress,
    city,
    province,
    postalCode,
  ].whereType<String>().where((part) => part.trim().isNotEmpty).join(', ');

  // Clone address with updated default flag
  AddressModel copyWith({bool? isDefault}) {
    return AddressModel(
      id: id,
      label: label,
      recipientName: recipientName,
      phoneNumber: phoneNumber,
      streetAddress: streetAddress,
      city: city,
      isDefault: isDefault ?? this.isDefault,
      province: province,
      postalCode: postalCode,
    );
  }
}
