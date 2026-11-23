import '../../../core/constants/api_endpoints.dart';

class ProductModel {
  final int id;
  final String name;
  final String description;
  final double price;
  final double? originalPrice;
  final int discountPercent;
  final double rating;
  final int reviewCount;
  final int categoryId;
  final int stock;
  final bool isActive;
  final String imageUrl;
  final bool isFavorite;

  const ProductModel({
    required this.id,
    required this.name,
    required this.description,
    required this.price,
    this.originalPrice,
    this.discountPercent = 0,
    required this.rating,
    required this.reviewCount,
    required this.categoryId,
    this.stock = 10,
    this.isActive = true,
    required this.imageUrl,
    this.isFavorite = false,
  });

  bool get isOutOfStock => !isActive || stock <= 0;
  bool get isLowStock => isActive && stock > 0 && stock <= 5;

  // Clone product with updated attributes
  ProductModel copyWith({bool? isFavorite, int? stock, bool? isActive}) {
    return ProductModel(
      id: id,
      name: name,
      description: description,
      price: price,
      originalPrice: originalPrice,
      discountPercent: discountPercent,
      rating: rating,
      reviewCount: reviewCount,
      categoryId: categoryId,
      stock: stock ?? this.stock,
      isActive: isActive ?? this.isActive,
      imageUrl: imageUrl,
      isFavorite: isFavorite ?? this.isFavorite,
    );
  }

  // Parse product from JSON map
  factory ProductModel.fromJson(Map<String, dynamic> json) {
    final rawPrice = (json['price'] as num?)?.toDouble() ?? 0.0;
    final discountPrice = (json['discount_price'] as num?)?.toDouble();
    final rawOriginalPrice = (json['original_price'] as num?)?.toDouble();

    double effectivePrice = rawPrice;
    double? effectiveOriginalPrice = rawOriginalPrice;
    int discountPct = (json['discount_percent'] as num?)?.toInt() ?? 0;

    if (discountPrice != null &&
        discountPrice > 0 &&
        discountPrice < rawPrice) {
      effectivePrice = discountPrice;
      effectiveOriginalPrice = rawPrice;
      discountPct = (((rawPrice - discountPrice) / rawPrice) * 100).round();
    } else if (rawOriginalPrice != null && rawOriginalPrice > rawPrice) {
      discountPct = (((rawOriginalPrice - rawPrice) / rawOriginalPrice) * 100)
          .round();
    }

    final productName = json['name'] as String? ?? '';
    final rawImage =
        json['image_url'] as String? ?? json['image'] as String? ?? '';
    final normalizedImage = ApiEndpoints.normalizeImageUrl(
      rawImage,
      fallbackName: productName,
    );

    return ProductModel(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: productName,
      description: json['description'] as String? ?? '',
      price: effectivePrice,
      originalPrice: effectiveOriginalPrice,
      discountPercent: discountPct,
      rating: (json['rating'] as num?)?.toDouble() ?? 0.0,
      reviewCount: (json['review_count'] as num?)?.toInt() ?? 0,
      categoryId: (json['category_id'] as num?)?.toInt() ?? 1,
      stock: json.containsKey('stock')
          ? ((json['stock'] as num?)?.toInt() ?? 0)
          : 10,
      isActive: json['is_active'] as bool? ?? true,
      imageUrl: normalizedImage,
      isFavorite: json['is_favorite'] as bool? ?? false,
    );
  }

  // Convert product to JSON map
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'price': price,
      'original_price': originalPrice,
      'discount_percent': discountPercent,
      'rating': rating,
      'review_count': reviewCount,
      'category_id': categoryId,
      'stock': stock,
      'is_active': isActive,
      'image_url': imageUrl,
      'is_favorite': isFavorite,
    };
  }
}
