import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../../../../shared/widgets/bouncing_button.dart';
import '../models/product_model.dart';

/// Card widget displaying product image, price, rating, and actions in grid views.
///
/// Designed with a compact vertical layout, square image area, high-contrast price
/// hierarchy, neat discount badges, and graceful fallback placeholders.
class ProductCard extends StatelessWidget {
  final ProductModel product;
  final VoidCallback onTap;
  final VoidCallback onToggleFavorite;
  final VoidCallback? onAddToCart;
  final Object? heroTag;

  const ProductCard({
    super.key,
    required this.product,
    required this.onTap,
    required this.onToggleFavorite,
    this.onAddToCart,
    this.heroTag,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return BouncingButton(
      onTap: onTap,
      scaleFactor: 0.97,
      child: Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF151D2C) : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isDark ? const Color(0xFF1E293B) : const Color(0xFFEDF2F7),
            width: 1.0,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: isDark ? 0.22 : 0.035),
              blurRadius: 12,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Square Thumbnail (aspectRatio: 1.0) with discount badge and favorite button
            Stack(
              children: [
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(15),
                  ),
                  child: AspectRatio(
                    aspectRatio: 1.0,
                    child: Container(
                      color: isDark
                          ? const Color(0xFF0F172A)
                          : const Color(0xFFF8FAFC),
                      child: Hero(
                        tag: heroTag ?? 'product-image-${product.id}',
                        child: _buildImage(isDark),
                      ),
                    ),
                  ),
                ),

                // Stock / Discount Badge (Top Left)
                if (product.isOutOfStock)
                  Positioned(
                    top: 6,
                    left: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2.5,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0F172A).withValues(alpha: 0.86),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        'OUT OF STOCK',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.2,
                        ),
                      ),
                    ),
                  )
                else if (product.discountPercent > 0)
                  Positioned(
                    top: 6,
                    left: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2.5,
                      ),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFFEF4444), Color(0xFFDC2626)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(6),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(
                              0xFFEF4444,
                            ).withValues(alpha: 0.3),
                            blurRadius: 4,
                            offset: const Offset(0, 1.5),
                          ),
                        ],
                      ),
                      child: Text(
                        '-${product.discountPercent}%',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 9.5,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.2,
                        ),
                      ),
                    ),
                  ),

                if (!product.isOutOfStock && product.isLowStock)
                  Positioned(
                    bottom: 6,
                    left: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2.5,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF59E0B).withValues(alpha: 0.92),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '${product.stock} left',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),

                // Favorite Heart Button (Top Right)
                Positioned(
                  top: 6,
                  right: 6,
                  child: Semantics(
                    button: true,
                    label: product.isFavorite
                        ? 'Remove from wishlist'
                        : 'Add to wishlist',
                    child: BouncingButton(
                      onTap: onToggleFavorite,
                      child: Container(
                        width: 30,
                        height: 30,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: isDark
                              ? const Color(0xFF0F172A).withValues(alpha: 0.85)
                              : Colors.white.withValues(alpha: 0.92),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: isDark
                                ? const Color(0xFF334155).withValues(alpha: 0.5)
                                : const Color(
                                    0xFFE2E8F0,
                                  ).withValues(alpha: 0.8),
                            width: 0.8,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(
                                alpha: isDark ? 0.25 : 0.05,
                              ),
                              blurRadius: 6,
                              offset: const Offset(0, 1.5),
                            ),
                          ],
                        ),
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 200),
                          transitionBuilder: (child, anim) =>
                              ScaleTransition(scale: anim, child: child),
                          child: Icon(
                            product.isFavorite
                                ? Icons.favorite_rounded
                                : Icons.favorite_border_rounded,
                            key: ValueKey<bool>(product.isFavorite),
                            size: 15,
                            color: product.isFavorite
                                ? const Color(0xFFEF4444)
                                : (isDark
                                      ? Colors.grey.shade400
                                      : const Color(0xFF64748B)),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),

            // Product details: rating, title, description, and price hierarchy
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 6),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Upper block: Rating pill + title + description
                    Flexible(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Rating Pill with review count (only when supported by real data)
                          if (product.rating > 0)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 2),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 4.5,
                                      vertical: 1,
                                    ),
                                    decoration: BoxDecoration(
                                      color: isDark
                                          ? const Color(
                                              0xFF78350F,
                                            ).withValues(alpha: 0.3)
                                          : const Color(0xFFFEF3C7),
                                      borderRadius: BorderRadius.circular(4),
                                      border: Border.all(
                                        color: isDark
                                            ? const Color(
                                                0xFFF59E0B,
                                              ).withValues(alpha: 0.25)
                                            : const Color(0xFFFDE68A),
                                        width: 0.7,
                                      ),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        const Icon(
                                          Icons.star_rounded,
                                          size: 11,
                                          color: Color(0xFFF59E0B),
                                        ),
                                        const SizedBox(width: 2),
                                        Text(
                                          product.rating.toStringAsFixed(1),
                                          style: TextStyle(
                                            fontSize: 9.5,
                                            fontWeight: FontWeight.w700,
                                            color: isDark
                                                ? const Color(0xFFFCD34D)
                                                : const Color(0xFF92400E),
                                          ),
                                        ),
                                        if (product.reviewCount > 0) ...[
                                          const SizedBox(width: 2),
                                          Text(
                                            '(${product.reviewCount})',
                                            style: TextStyle(
                                              fontSize: 8.5,
                                              fontWeight: FontWeight.w500,
                                              color: isDark
                                                  ? const Color(
                                                      0xFFFCD34D,
                                                    ).withValues(alpha: 0.75)
                                                  : const Color(0xFFB45309),
                                            ),
                                          ),
                                        ],
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),

                          // Title with neat line height
                          Text(
                            product.name,
                            maxLines: product.description.isNotEmpty ? 1 : 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              height: 1.15,
                              color: isDark
                                  ? Colors.white
                                  : const Color(0xFF0F172A),
                              letterSpacing: -0.2,
                            ),
                          ),

                          // Subtitle / Product description snippet
                          if (product.description.isNotEmpty) ...[
                            const SizedBox(height: 1.5),
                            Text(
                              product.description,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w400,
                                height: 1.15,
                                color: isDark
                                    ? const Color(0xFF94A3B8)
                                    : const Color(0xFF64748B),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),

                    // Lower block: Clear Price Hierarchy
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Text(
                          '\$${product.price.toStringAsFixed(2)}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w900,
                            color: Color(0xFF2563EB),
                            letterSpacing: -0.3,
                          ),
                        ),
                        if (product.originalPrice != null &&
                            product.originalPrice! > product.price) ...[
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              '\$${product.originalPrice!.toStringAsFixed(2)}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 10,
                                color: isDark
                                    ? Colors.grey.shade500
                                    : const Color(0xFF94A3B8),
                                decoration: TextDecoration.lineThrough,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImage(bool isDark) {
    if (product.imageUrl.isEmpty) {
      return _buildImagePlaceholder(isDark);
    }

    if (product.imageUrl.startsWith('assets/')) {
      return Image.asset(
        product.imageUrl,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) =>
            _buildImagePlaceholder(isDark),
      );
    }

    return Image.network(
      product.imageUrl,
      fit: BoxFit.cover,
      cacheWidth: 450,
      loadingBuilder: (context, child, progress) {
        if (progress == null) return child;
        return Shimmer.fromColors(
          baseColor: isDark
              ? const Color(0xFF1E293B)
              : const Color(0xFFF1F5F9),
          highlightColor: isDark
              ? const Color(0xFF334155)
              : const Color(0xFFFFFFFF),
          child: Container(
            color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
          ),
        );
      },
      errorBuilder: (context, error, stackTrace) =>
          _buildImagePlaceholder(isDark),
    );
  }

  Widget _buildImagePlaceholder(bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? [const Color(0xFF1E293B), const Color(0xFF0F172A)]
              : [const Color(0xFFF8FAFC), const Color(0xFFE2E8F0)],
        ),
      ),
      alignment: Alignment.center,
      child: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: isDark
              ? const Color(0xFF2563EB).withValues(alpha: 0.14)
              : const Color(0xFFEFF6FF),
          border: Border.all(
            color: isDark
                ? const Color(0xFF2563EB).withValues(alpha: 0.28)
                : const Color(0xFFBFDBFE),
            width: 0.8,
          ),
        ),
        child: const Icon(
          Icons.shopping_bag_outlined,
          color: Color(0xFF2563EB),
          size: 19,
        ),
      ),
    );
  }
}
