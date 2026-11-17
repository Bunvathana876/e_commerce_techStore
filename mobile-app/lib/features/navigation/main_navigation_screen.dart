import 'package:e_commerc_mobile_app/features/home/screens/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../shared/widgets/app_bottom_nav_bar.dart';
import '../cart/providers/cart_provider.dart';
import '../cart/screens/cart_screen.dart';
import '../categories/screens/categories_screen.dart';
import '../favorites/screens/favorites_screen.dart';
import '../products/providers/product_provider.dart';
import '../profile/screens/profile_screen.dart';

// Main app shell with bottom navigation bar
class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    // Badge counts for cart and favorites
    final cartCount = context.watch<CartProvider>().totalItemsCount;
    final favCount = context.watch<ProductProvider>().totalFavoritesCount;

    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Navigation destinations
    final screens = [
      HomeScreen(
        onSeeAllCategories: () => setState(() => _currentIndex = 1),
        onProfileTap: () => setState(() => _currentIndex = 4),
      ),
      CategoriesScreen(
        onCategorySelected: (catId) {
          context.read<ProductProvider>().selectCategory(catId);
          setState(() => _currentIndex = 0);
        },
      ),
      FavoritesScreen(onExplore: () => setState(() => _currentIndex = 0)),
      CartScreen(onExplore: () => setState(() => _currentIndex = 0)),
      const ProfileScreen(),
    ];

    final navItems = [
      const AppNavItem(
        label: 'Home',
        activeIcon: Icons.home_rounded,
        inactiveIcon: Icons.home_outlined,
      ),
      const AppNavItem(
        label: 'Categories',
        activeIcon: Icons.grid_view_rounded,
        inactiveIcon: Icons.grid_view_outlined,
      ),
      AppNavItem(
        label: 'Favorites',
        activeIcon: Icons.favorite_rounded,
        inactiveIcon: Icons.favorite_outline_rounded,
        badgeCount: favCount,
      ),
      AppNavItem(
        label: 'Cart',
        activeIcon: Icons.shopping_bag_rounded,
        inactiveIcon: Icons.shopping_bag_outlined,
        badgeCount: cartCount,
      ),
      const AppNavItem(
        label: 'Profile',
        activeIcon: Icons.person_rounded,
        inactiveIcon: Icons.person_outline_rounded,
      ),
    ];

    return Scaffold(
      extendBody: false,
      backgroundColor: isDark
          ? const Color(0xFF0B0F19)
          : const Color(0xFFF5F7FB),
      body: Stack(
        children: [
          // Subtle ambient glow in top safe area for depth without noise
          Positioned(
            top: -100,
            left: -40,
            right: -40,
            height: 280,
            child: Container(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    const Color(
                      0xFF2563EB,
                    ).withValues(alpha: isDark ? 0.15 : 0.08),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),

          // Active tab screen
          IndexedStack(index: _currentIndex, children: screens),
        ],
      ),
      // Clean, modern floating-style rounded bottom navigation bar with notification badges
      bottomNavigationBar: AppBottomNavBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: navItems,
      ),
    );
  }
}
