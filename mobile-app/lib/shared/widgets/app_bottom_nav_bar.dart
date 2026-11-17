import 'package:flutter/material.dart';

/// Navigation item model for [AppBottomNavBar].
class AppNavItem {
  final String label;
  final IconData activeIcon;
  final IconData inactiveIcon;
  final int badgeCount;

  const AppNavItem({
    required this.label,
    required this.activeIcon,
    required this.inactiveIcon,
    this.badgeCount = 0,
  });
}

/// Premium, compact, floating-style bottom navigation bar.
///
/// Features a rounded outer container (~28px border radius), subtle border,
/// gentle elevation, soft-blue active state background, consistent icon sizing,
/// and smooth transitions respecting reduced-motion accessibility settings.
class AppBottomNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<AppNavItem> items;
  final double borderRadius;
  final double horizontalMargin;
  final double height;
  final Color? backgroundColor;
  final Color? borderColor;
  final Color activeColor;
  final Color? inactiveColor;
  final Duration animationDuration;

  const AppBottomNavBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.items,
    this.borderRadius = 28.0,
    this.horizontalMargin = 16.0,
    this.height = 58.0,
    this.backgroundColor,
    this.borderColor,
    this.activeColor = const Color(0xFF2563EB),
    this.inactiveColor,
    this.animationDuration = const Duration(milliseconds: 200),
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final disableAnimations =
        MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    final animDuration =
        disableAnimations ? Duration.zero : animationDuration;

    final bg = backgroundColor ??
        (isDark ? const Color(0xFF1E293B) : Colors.white);
    final border = borderColor ??
        (isDark
            ? const Color(0xFF334155).withValues(alpha: 0.6)
            : const Color(0xFFE2E8F0));
    final inactive = inactiveColor ??
        (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B));

    return SafeArea(
      top: false,
      bottom: true,
      minimum: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: horizontalMargin),
        child: Container(
          height: height,
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(color: border, width: 1.0),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.30 : 0.06),
                blurRadius: 16,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            children: List.generate(items.length, (index) {
              final item = items[index];
              final isSelected = index == currentIndex;

              return Expanded(
                child: _buildTabItem(
                  context: context,
                  index: index,
                  item: item,
                  isSelected: isSelected,
                  isDark: isDark,
                  activeColor: activeColor,
                  inactiveColor: inactive,
                  animDuration: animDuration,
                ),
              );
            }),
          ),
        ),
      ),
    );
  }

  Widget _buildTabItem({
    required BuildContext context,
    required int index,
    required AppNavItem item,
    required bool isSelected,
    required bool isDark,
    required Color activeColor,
    required Color inactiveColor,
    required Duration animDuration,
  }) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => onTap(index),
      child: Center(
        child: AnimatedContainer(
          duration: animDuration,
          curve: Curves.easeInOutCubic,
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 4.0),
          decoration: BoxDecoration(
            color: isSelected
                ? activeColor.withValues(alpha: isDark ? 0.20 : 0.09)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildIconWithBadge(
                item,
                isSelected,
                activeColor,
                inactiveColor,
                isDark,
              ),
              const SizedBox(height: 2.5),
              AnimatedDefaultTextStyle(
                duration: animDuration,
                curve: Curves.easeInOutCubic,
                style: TextStyle(
                  fontSize: 10.0,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  color: isSelected ? activeColor : inactiveColor,
                  letterSpacing: -0.3,
                ),
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    item.label,
                    maxLines: 1,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIconWithBadge(
    AppNavItem item,
    bool isSelected,
    Color activeColor,
    Color inactiveColor,
    bool isDark,
  ) {
    final iconWidget = Icon(
      isSelected ? item.activeIcon : item.inactiveIcon,
      size: 22.5,
      color: isSelected ? activeColor : inactiveColor,
    );

    if (item.badgeCount <= 0) {
      return iconWidget;
    }

    return Stack(
      clipBehavior: Clip.none,
      children: [
        iconWidget,
        Positioned(
          top: -3,
          right: -7,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 3.5, vertical: 1),
            constraints: const BoxConstraints(minWidth: 14, minHeight: 14),
            decoration: BoxDecoration(
              color: const Color(0xFFEF4444),
              borderRadius: BorderRadius.circular(7),
              border: Border.all(
                color: isDark ? const Color(0xFF1E293B) : Colors.white,
                width: 1.5,
              ),
            ),
            child: Text(
              item.badgeCount > 99 ? '99+' : '${item.badgeCount}',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 8.5,
                fontWeight: FontWeight.w800,
                color: Colors.white,
                height: 1,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
