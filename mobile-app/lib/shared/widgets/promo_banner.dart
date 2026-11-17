import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import 'bouncing_button.dart';

/// Full-bleed editorial promotional banner card with rich photographic background,
/// subtle directional gradient overlay, bold typography, and compact capsule pill CTA.
class PromoBanner extends StatelessWidget {
  final String? title;
  final String titlePrefix;
  final String highlightText;
  final String titleSuffix;
  final String subtitle;
  final String couponCode;
  final String buttonText;
  final String? imageUrl;
  final String? assetPath;
  final VoidCallback? onTap;
  final Color accentColor;
  final int activeDotIndex;
  final int totalDots;
  final String? tag;
  final IconData? tagIcon;
  final String? badgeText;
  final double? height;
  final EdgeInsetsGeometry? margin;

  const PromoBanner({
    super.key,
    this.title,
    this.titlePrefix = '',
    this.highlightText = '',
    this.titleSuffix = '',
    this.subtitle = '',
    this.couponCode = '',
    this.buttonText = 'Explore',
    this.imageUrl,
    this.assetPath,
    this.onTap,
    this.accentColor = const Color(0xFF059669),
    this.activeDotIndex = 0,
    this.totalDots = 3,
    this.tag,
    this.tagIcon,
    this.badgeText,
    this.height,
    this.margin,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final titleColor = isDark ? Colors.white : const Color(0xFF0F172A);
    final subColor = isDark ? const Color(0xFFCBD5E1) : const Color(0xFF475569);

    return Container(
      margin: margin ?? const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      height: height ?? 185,
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isDark
              ? const Color(0xFF334155).withValues(alpha: 0.5)
              : const Color(0xFFE2E8F0),
          width: 1.0,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.30 : 0.04),
            blurRadius: 14,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // 1. Full-bleed background photographic image filling the ENTIRE card
            Positioned.fill(
              child: _buildBannerImage(isDark),
            ),

            // 2. Subtle directional gradient overlay (opaque on left, transparent on right)
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                    stops: const [0.0, 0.40, 0.70, 1.0],
                    colors: isDark
                        ? [
                            const Color(0xFF0B1120).withValues(alpha: 0.94),
                            const Color(0xFF0B1120).withValues(alpha: 0.82),
                            const Color(0xFF0B1120).withValues(alpha: 0.30),
                            Colors.transparent,
                          ]
                        : [
                            Colors.white.withValues(alpha: 0.95),
                            Colors.white.withValues(alpha: 0.85),
                            Colors.white.withValues(alpha: 0.28),
                            Colors.transparent,
                          ],
                  ),
                ),
              ),
            ),

            // 3. Editorial Badge (top right, if provided)
            if (badgeText != null && badgeText!.isNotEmpty)
              Positioned(
                top: 14,
                right: 14,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3.5,
                  ),
                  decoration: BoxDecoration(
                    color: isDark
                        ? const Color(0xFF0F172A).withValues(alpha: 0.85)
                        : Colors.white.withValues(alpha: 0.92),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isDark
                          ? Colors.white.withValues(alpha: 0.15)
                          : Colors.black.withValues(alpha: 0.08),
                      width: 0.8,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.06),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                  child: Text(
                    badgeText!.toUpperCase(),
                    style: TextStyle(
                      fontSize: 8.5,
                      fontWeight: FontWeight.w800,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                      letterSpacing: 0.6,
                    ),
                  ),
                ),
              ),

            // 4. Content Area on the Left (constrained to avoid covering the subject)
            Positioned.fill(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 14, 18, 14),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final contentWidth = (constraints.maxWidth * 0.62)
                        .clamp(170.0, 260.0);
                    return Align(
                      alignment: Alignment.centerLeft,
                      child: SizedBox(
                        width: contentWidth,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            // Top Section: Tag pill, Headline & Subtitle
                            Flexible(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  if (tag != null && tag!.isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(bottom: 6),
                                      child: Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 7.5,
                                          vertical: 2.5,
                                        ),
                                        decoration: BoxDecoration(
                                          color: accentColor.withValues(
                                            alpha: isDark ? 0.22 : 0.12,
                                          ),
                                          borderRadius: BorderRadius.circular(14),
                                        ),
                                        child: Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            if (tagIcon != null) ...[
                                              Icon(
                                                tagIcon,
                                                size: 10,
                                                color: accentColor,
                                              ),
                                              const SizedBox(width: 3.5),
                                            ],
                                            Text(
                                              tag!.toUpperCase(),
                                              style: TextStyle(
                                                fontSize: 9,
                                                fontWeight: FontWeight.w800,
                                                color: accentColor,
                                                letterSpacing: 0.5,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),

                                  // Bold Editorial Headline
                                  _buildHeadline(context, titleColor),

                                  // Clear supporting text
                                  if (subtitle.isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 3.5),
                                      child: Text(
                                        subtitle,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.w400,
                                          color: subColor,
                                          height: 1.25,
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            ),

                            // Bottom Section: Capsule Pill CTA Button
                            BouncingButton(
                              onTap: onTap,
                              scaleFactor: 0.95,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 8,
                                ),
                                decoration: BoxDecoration(
                                  color: isDark
                                      ? Colors.white
                                      : const Color(0xFF0F172A),
                                  borderRadius: BorderRadius.circular(999),
                                  border: Border.all(
                                    color: isDark
                                        ? Colors.white.withValues(alpha: 0.15)
                                        : Colors.black.withValues(alpha: 0.10),
                                    width: 0.8,
                                  ),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.black.withValues(
                                        alpha: isDark ? 0.30 : 0.08,
                                      ),
                                      blurRadius: 6,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(
                                      buttonText,
                                      style: TextStyle(
                                        color: isDark
                                            ? const Color(0xFF0F172A)
                                            : Colors.white,
                                        fontSize: 12,
                                        fontWeight: FontWeight.w700,
                                        letterSpacing: -0.1,
                                      ),
                                    ),
                                    const SizedBox(width: 5),
                                    Icon(
                                      Icons.arrow_forward_rounded,
                                      size: 13,
                                      color: isDark
                                          ? const Color(0xFF0F172A)
                                          : Colors.white,
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),

            // 5. Carousel Pagination Dots (positioned on bottom-right, never covering CTA)
            if (totalDots > 1)
              Positioned(
                bottom: 14,
                right: 18,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: List.generate(totalDots, (index) {
                    final isActive = index == activeDotIndex;
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      curve: Curves.easeOutCubic,
                      margin: const EdgeInsets.symmetric(horizontal: 2),
                      width: isActive ? 14 : 4.5,
                      height: 4.5,
                      decoration: BoxDecoration(
                        color: isActive
                            ? (isDark
                                ? Colors.white
                                : const Color(0xFF0F172A))
                            : (isDark
                                ? Colors.white.withValues(alpha: 0.25)
                                : Colors.black.withValues(alpha: 0.18)),
                        borderRadius: BorderRadius.circular(3),
                      ),
                    );
                  }),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeadline(BuildContext context, Color titleColor) {
    final textScaler = MediaQuery.maybeTextScalerOf(context) ?? TextScaler.noScaling;

    if (title != null && title!.isNotEmpty) {
      return Text(
        title!,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        textScaler: textScaler,
        style: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w800,
          color: titleColor,
          height: 1.18,
          letterSpacing: -0.4,
        ),
      );
    }

    return RichText(
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
      textScaler: textScaler,
      text: TextSpan(
        style: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w800,
          color: titleColor,
          height: 1.18,
          letterSpacing: -0.4,
        ),
        children: [
          if (titlePrefix.isNotEmpty) TextSpan(text: titlePrefix),
          if (highlightText.isNotEmpty)
            TextSpan(
              text: highlightText,
              style: TextStyle(color: accentColor),
            ),
          if (titleSuffix.isNotEmpty) TextSpan(text: titleSuffix),
        ],
      ),
    );
  }

  Widget _buildBannerImage(bool isDark) {
    if (assetPath != null && assetPath!.isNotEmpty) {
      return Image.asset(
        assetPath!,
        fit: BoxFit.cover,
        alignment: Alignment.centerRight,
        errorBuilder: (context, error, stackTrace) => _fallbackImage(isDark),
      );
    }

    if (imageUrl != null && imageUrl!.isNotEmpty) {
      return Image.network(
        imageUrl!,
        fit: BoxFit.cover,
        alignment: Alignment.centerRight,
        loadingBuilder: (context, child, progress) {
          if (progress == null) return child;
          return Shimmer.fromColors(
            baseColor: isDark
                ? const Color(0xFF1E293B)
                : const Color(0xFFE2E8F0),
            highlightColor: isDark
                ? const Color(0xFF334155)
                : const Color(0xFFF8FAFC),
            child: Container(
              color: Colors.white,
              width: double.infinity,
              height: double.infinity,
            ),
          );
        },
        errorBuilder: (context, error, stackTrace) => _fallbackImage(isDark),
      );
    }

    return _fallbackImage(isDark);
  }

  Widget _fallbackImage(bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? [const Color(0xFF1E293B), const Color(0xFF0F172A)]
              : [const Color(0xFFF1F5F9), const Color(0xFFE2E8F0)],
        ),
      ),
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.only(right: 32),
      child: Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          color: accentColor.withValues(alpha: 0.12),
          shape: BoxShape.circle,
        ),
        child: Icon(Icons.shopping_bag_outlined, size: 28, color: accentColor),
      ),
    );
  }
}
