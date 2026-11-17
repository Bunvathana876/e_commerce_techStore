import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shimmer/shimmer.dart';

import '../../../core/constants/api_endpoints.dart';
import '../../../core/utils/page_transitions.dart';
import '../../../shared/widgets/app_logo.dart';
import '../../../shared/widgets/app_search_bar.dart';
import '../../../shared/widgets/bouncing_button.dart';
import '../../../shared/widgets/promo_banner_carousel.dart';
import '../../auth/models/user_model.dart';
import '../../auth/providers/auth_provider.dart';
import '../../cart/providers/cart_provider.dart';
import '../../categories/models/category_model.dart';
import '../../categories/providers/category_provider.dart';
import '../../categories/screens/categories_screen.dart';
import '../../notifications/providers/notification_provider.dart';
import '../../notifications/screens/notifications_screen.dart';
import '../../products/models/product_model.dart';
import '../../products/providers/product_provider.dart';
import '../../products/screens/product_detail_screen.dart';
import '../../products/widgets/product_grid.dart';
import '../../profile/screens/profile_screen.dart';

/// Premium Blue Panda Home storefront screen.
///
/// Refined with compact spacing, square product imagery, cohesive Material
/// category iconography, legible category labels, and responsive 2-column product grid.
class HomeScreen extends StatefulWidget {
  final VoidCallback? onSeeAllCategories;
  final VoidCallback? onMenuTap;
  final VoidCallback? onProfileTap;

  const HomeScreen({
    super.key,
    this.onSeeAllCategories,
    this.onMenuTap,
    this.onProfileTap,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entranceController;
  late final Animation<double> _fadeAnimation;
  late final Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _entranceController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );
    _fadeAnimation = CurvedAnimation(
      parent: _entranceController,
      curve: Curves.easeOut,
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.02),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _entranceController,
        curve: Curves.easeOutCubic,
      ),
    );
    _entranceController.forward();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.of(context).disableAnimations) {
      _entranceController.value = 1.0;
    }
  }

  @override
  void dispose() {
    _entranceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final productProvider = context.watch<ProductProvider>();
    final categoryProvider = context.watch<CategoryProvider>();
    final displayedProducts = productProvider.displayedProducts;
    final totalProducts = productProvider.filteredProducts.length;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final selectedCategory = categoryProvider.allCategories.firstWhere(
      (c) => c.id == productProvider.selectedCategoryId,
      orElse: () => const CategoryModel(
        id: 0,
        name: 'All Items',
        icon: '🔥',
        itemCount: 0,
        imageUrl: '',
      ),
    );

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: SlideTransition(
            position: _slideAnimation,
            child: NotificationListener<ScrollNotification>(
              onNotification: (ScrollNotification scrollInfo) {
                // Lazy load below the fold when user scrolls within 350px of the bottom
                if (scrollInfo.metrics.axis == Axis.vertical &&
                    scrollInfo.metrics.pixels >=
                        scrollInfo.metrics.maxScrollExtent - 350) {
                  if (productProvider.hasMore &&
                      !productProvider.isLoadingMore) {
                    productProvider.loadMore();
                  }
                }
                return false;
              },
              child: RefreshIndicator(
                color: const Color(0xFF2563EB),
                backgroundColor: isDark ? const Color(0xFF1E293B) : Colors.white,
                onRefresh: () async {
                  await Future.wait([
                    productProvider.loadFromBackend(force: true),
                    categoryProvider.loadFromBackend(),
                  ]);
                },
                child: CustomScrollView(
                  physics: const AlwaysScrollableScrollPhysics(
                    parent: BouncingScrollPhysics(),
                  ),
                  slivers: [
                    // Minimal editorial search and top navigation header
                    _HomeSearchBarHeader(
                      isDark: isDark,
                      searchQuery: productProvider.searchQuery,
                      onSearchChanged: productProvider.setSearchQuery,
                      onNotificationTap: () {
                        Navigator.of(context).push(
                          SmoothPageRoute(
                            page: const NotificationsScreen(),
                          ),
                        );
                      },
                      onProfileTap: widget.onProfileTap ??
                          () {
                            Navigator.of(context).push(
                              SmoothPageRoute(
                                page: const ProfileScreen(),
                              ),
                            );
                          },
                      onFilterTap: () => _showSortFilterModal(
                        context,
                        productProvider,
                        isDark,
                      ),
                    ),

                    // Offline / Error state when backend is unreachable and catalog is empty
                    if (!productProvider.isLoading &&
                        productProvider.errorMessage != null &&
                        displayedProducts.isEmpty)
                      SliverFillRemaining(
                        hasScrollBody: false,
                        child: _HomeErrorState(
                          isDark: isDark,
                          message: productProvider.errorMessage!,
                          onRetry: () {
                            productProvider.loadFromBackend(force: true);
                            categoryProvider.loadFromBackend();
                          },
                        ),
                      )
                    else ...[
                      // Promotional banner carousel with curated campaigns
                      _HomePromoCarousel(
                        onCategorySelected: (catId) =>
                            productProvider.selectCategory(catId),
                      ),

                      // Horizontal category rail or skeleton loader
                      if (categoryProvider.isLoading &&
                          categoryProvider.allCategories.isEmpty)
                        _HomeCategoriesShimmer(isDark: isDark)
                      else if (categoryProvider.allCategories.isNotEmpty)
                        _HomeCategoriesBar(
                          isDark: isDark,
                          categories: categoryProvider.allCategories,
                          selectedCategoryId: productProvider.selectedCategoryId,
                          onCategorySelected: (catId) {
                            categoryProvider.selectCategory(catId);
                            productProvider.selectCategory(catId);
                          },
                          onSeeAll: () {
                            if (widget.onSeeAllCategories != null) {
                              widget.onSeeAllCategories!();
                            } else {
                              Navigator.of(context).push(
                                SmoothPageRoute(
                                  page: const CategoriesScreen(),
                                ),
                              );
                            }
                          },
                        ),

                      // Popular products section header with count and sort pill
                      _HomeSectionHeader(
                        isDark: isDark,
                        title: 'Popular Items',
                        subtitle: totalProducts == displayedProducts.length
                            ? '$totalProducts items'
                            : 'Showing ${displayedProducts.length} of $totalProducts',
                        activeSort: _sortLabel(productProvider.sortBy),
                        onSortTap: () => _showSortFilterModal(
                          context,
                          productProvider,
                          isDark,
                        ),
                      ),

                      // Active filter chips row when category, search, or sort is active
                      if (productProvider.selectedCategoryId != 0 ||
                          productProvider.searchQuery.isNotEmpty ||
                          productProvider.sortBy != 'default')
                        SliverToBoxAdapter(
                          child: _HomeActiveFilterBar(
                            isDark: isDark,
                            categoryName: productProvider.selectedCategoryId != 0
                                ? selectedCategory.name
                                : null,
                            searchQuery: productProvider.searchQuery.isNotEmpty
                                ? productProvider.searchQuery
                                : null,
                            sortLabel: productProvider.sortBy != 'default'
                                ? _sortLabel(productProvider.sortBy)
                                : null,
                            onClearCategory: () {
                              categoryProvider.selectCategory(0);
                              productProvider.selectCategory(0);
                            },
                            onClearSearch: () =>
                                productProvider.setSearchQuery(''),
                            onClearSort: () =>
                                productProvider.setSortBy('default'),
                            onResetAll: () {
                              categoryProvider.selectCategory(0);
                              productProvider.resetFilters();
                            },
                          ),
                        ),

                      // Skeleton shimmer grid during initial load or 2-column product grid
                      if (productProvider.isLoading &&
                          displayedProducts.isEmpty)
                        _HomeShimmerGrid(isDark: isDark)
                      else
                        _HomeProductGrid(
                          isDark: isDark,
                          products: displayedProducts,
                          onToggleFavorite: productProvider.toggleFavorite,
                          onAddToCart: (product) {
                            context.read<CartProvider>().addItem(
                              product,
                              quantity: 1,
                            );
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Added ${product.name} to cart!'),
                                duration: const Duration(seconds: 1),
                                behavior: SnackBarBehavior.floating,
                              ),
                            );
                          },
                          onResetFilters: () {
                            categoryProvider.selectCategory(0);
                            productProvider.resetFilters();
                          },
                        ),
                    ],

                    // Infinite scroll loading spinner or end-of-list marker
                    if (productProvider.isLoadingMore)
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 20),
                          child: Center(
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.2,
                                    color: Color(0xFF2563EB),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  'Loading more items...',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: isDark
                                        ? Colors.grey.shade400
                                        : Colors.grey.shade600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      )
                    else if (!productProvider.hasMore &&
                        displayedProducts.length >= 6)
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(20, 10, 20, 28),
                          child: Center(
                            child: Text(
                              "You've viewed all $totalProducts products ✓",
                              style: TextStyle(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w500,
                                color: isDark
                                    ? Colors.grey.shade500
                                    : Colors.grey.shade400,
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static String _sortLabel(String sortId) {
    switch (sortId) {
      case 'price_low':
        return 'Price: Low to High';
      case 'price_high':
        return 'Price: High to Low';
      case 'rating':
        return 'Top Rated';
      default:
        return 'Popular';
    }
  }

  static void _showSortFilterModal(
    BuildContext context,
    ProductProvider provider,
    bool isDark,
  ) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: isDark ? const Color(0xFF151D2C) : Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        final sorts = [
          {
            'id': 'default',
            'label': 'Popular & Featured',
            'icon': Icons.local_fire_department_rounded,
          },
          {
            'id': 'price_low',
            'label': 'Price: Low to High',
            'icon': Icons.arrow_upward_rounded,
          },
          {
            'id': 'price_high',
            'label': 'Price: High to Low',
            'icon': Icons.arrow_downward_rounded,
          },
          {
            'id': 'rating',
            'label': 'Customer Rating',
            'icon': Icons.star_rounded,
          },
        ];

        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 38,
                    height: 4,
                    decoration: BoxDecoration(
                      color: isDark
                          ? Colors.grey.shade700
                          : Colors.grey.shade300,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Sort Products',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                      ),
                    ),
                    if (provider.sortBy != 'default')
                      GestureDetector(
                        onTap: () {
                          provider.setSortBy('default');
                          Navigator.of(context).pop();
                        },
                        child: const Text(
                          'Reset',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF2563EB),
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                ...sorts.map((sort) {
                  final isSelected = provider.sortBy == sort['id'];
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        color: isSelected
                            ? const Color(0xFF2563EB).withValues(alpha: 0.15)
                            : (isDark
                                ? const Color(0xFF1E293B)
                                : const Color(0xFFF1F5F9)),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        sort['icon'] as IconData,
                        size: 18,
                        color: isSelected
                            ? const Color(0xFF2563EB)
                            : (isDark
                                ? Colors.grey.shade400
                                : const Color(0xFF64748B)),
                      ),
                    ),
                    title: Text(
                      sort['label'] as String,
                      style: TextStyle(
                        fontSize: 14.5,
                        fontWeight: isSelected
                            ? FontWeight.w700
                            : FontWeight.w500,
                        color: isSelected
                            ? const Color(0xFF2563EB)
                            : (isDark ? Colors.white : const Color(0xFF0F172A)),
                      ),
                    ),
                    trailing: isSelected
                        ? const Icon(
                            Icons.check_circle_rounded,
                            color: Color(0xFF2563EB),
                            size: 20,
                          )
                        : null,
                    onTap: () {
                      provider.setSortBy(sort['id'] as String);
                      Navigator.of(context).pop();
                    },
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// Minimal editorial search bar, top navigation, and profile header.
class _HomeSearchBarHeader extends StatefulWidget {
  final bool isDark;
  final String searchQuery;
  final ValueChanged<String> onSearchChanged;
  final VoidCallback onNotificationTap;
  final VoidCallback onProfileTap;
  final VoidCallback? onFilterTap;

  const _HomeSearchBarHeader({
    required this.isDark,
    required this.onSearchChanged,
    required this.onNotificationTap,
    required this.onProfileTap,
    this.searchQuery = '',
    this.onFilterTap,
  });

  @override
  State<_HomeSearchBarHeader> createState() => _HomeSearchBarHeaderState();
}

class _HomeSearchBarHeaderState extends State<_HomeSearchBarHeader> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.searchQuery);
  }

  @override
  void didUpdateWidget(covariant _HomeSearchBarHeader oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.searchQuery != _controller.text) {
      _controller.text = widget.searchQuery;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    int unreadCount = 0;
    try {
      unreadCount = context.watch<NotificationProvider>().unreadCount;
    } catch (_) {}

    UserModel? user;
    try {
      user = context.watch<AuthProvider>().currentUser;
    } catch (_) {}

    final buttonBg = widget.isDark
        ? const Color(0xFF1E293B)
        : const Color(0xFFF1F5F9);
    final buttonBorder = widget.isDark
        ? const Color(0xFF334155).withValues(alpha: 0.5)
        : const Color(0xFFE2E8F0);
    final iconColor = widget.isDark
        ? Colors.white
        : const Color(0xFF0F172A);

    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 14),
        child: Column(
          children: [
            // Top navigation row
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // LEFT: Brand identity (AppLogo + Store Name)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const AppLogo(size: 34, borderRadius: 9),
                    const SizedBox(width: 8),
                    Text(
                      'Blue Panda',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.4,
                        color: widget.isDark
                            ? Colors.white
                            : const Color(0xFF0F172A),
                      ),
                    ),
                  ],
                ),

                // RIGHT: Notification button + User profile avatar
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Circular, light-gray notification button
                    BouncingButton(
                      onTap: widget.onNotificationTap,
                      child: Container(
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          color: buttonBg,
                          shape: BoxShape.circle,
                          border: Border.all(color: buttonBorder, width: 1.0),
                        ),
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            Icon(
                              Icons.notifications_none_rounded,
                              size: 22,
                              color: iconColor,
                            ),
                            if (unreadCount > 0)
                              Positioned(
                                top: 10,
                                right: 10,
                                child: Container(
                                  width: 8.5,
                                  height: 8.5,
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFEF4444),
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                      color: buttonBg,
                                      width: 1.5,
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),

                    // Circular user profile avatar
                    BouncingButton(
                      onTap: widget.onProfileTap,
                      child: _buildAvatar(user, buttonBg, buttonBorder, iconColor),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Search row: Wide, soft-gray rounded search field + Separate circular black filter button
            Row(
              children: [
                Expanded(
                  child: AppSearchBar(
                    controller: _controller,
                    onChanged: (val) {
                      widget.onSearchChanged(val);
                      setState(() {});
                    },
                    borderRadius: BorderRadius.circular(28),
                    hintText: "What's on your list?",
                  ),
                ),
                const SizedBox(width: 12),

                // Separate circular black filter button on the right
                BouncingButton(
                  onTap: widget.onFilterTap ?? () {},
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: widget.isDark
                          ? Colors.white
                          : const Color(0xFF0F172A),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(
                            alpha: widget.isDark ? 0.25 : 0.08,
                          ),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Center(
                      child: Icon(
                        Icons.tune_rounded,
                        size: 20,
                        color: widget.isDark
                            ? const Color(0xFF0F172A)
                            : Colors.white,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAvatar(
    UserModel? user,
    Color bg,
    Color border,
    Color iconColor,
  ) {
    final avatarUrl = user?.avatarUrl;
    final normalizedUrl = (avatarUrl != null && avatarUrl.trim().isNotEmpty)
        ? ApiEndpoints.normalizeImageUrl(avatarUrl.trim())
        : null;

    if (normalizedUrl != null && normalizedUrl.isNotEmpty) {
      return Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          color: bg,
          shape: BoxShape.circle,
          border: Border.all(color: border, width: 1.0),
        ),
        child: ClipOval(
          child: Image.network(
            normalizedUrl,
            width: 46,
            height: 46,
            fit: BoxFit.cover,
            errorBuilder: (context, error, stackTrace) =>
                _buildFallbackContent(user, iconColor),
          ),
        ),
      );
    }

    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        color: bg,
        shape: BoxShape.circle,
        border: Border.all(color: border, width: 1.0),
      ),
      child: Center(
        child: _buildFallbackContent(user, iconColor),
      ),
    );
  }

  Widget _buildFallbackContent(UserModel? user, Color iconColor) {
    if (user != null && user.fullName.trim().isNotEmpty) {
      final initial = user.fullName.trim().characters.first.toUpperCase();
      return Text(
        initial,
        style: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: iconColor,
          letterSpacing: -0.2,
        ),
      );
    }

    return Icon(
      Icons.person_outline_rounded,
      size: 22,
      color: iconColor,
    );
  }
}

/// Promotional banners carousel connected to real store campaigns.
class _HomePromoCarousel extends StatelessWidget {
  final ValueChanged<int> onCategorySelected;

  const _HomePromoCarousel({required this.onCategorySelected});

  List<PromoItem> _buildBanners() {
    return [
      PromoItem(
        titlePrefix: 'Curated ',
        highlightText: 'Summer ',
        titleSuffix: 'Styles',
        subtitle: 'Explore minimal essentials & fresh apparel',
        buttonText: 'Discover',
        accentColor: const Color(0xFF059669),
        tag: 'NEW COLLECTION',
        tagIcon: Icons.auto_awesome_rounded,
        badgeText: 'FEATURED',
        imageUrl:
            'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600&q=80',
        onTap: () => onCategorySelected(2),
      ),
      PromoItem(
        titlePrefix: 'Next-Gen ',
        highlightText: 'Audio ',
        titleSuffix: '& Tech',
        subtitle: 'Studio headphones, 4K displays & gear',
        buttonText: 'Shop Tech',
        accentColor: const Color(0xFF2563EB),
        tag: 'WORKSPACE EDIT',
        tagIcon: Icons.headphones_rounded,
        badgeText: 'POPULAR',
        imageUrl:
            'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&q=80',
        onTap: () => onCategorySelected(1),
      ),
      PromoItem(
        titlePrefix: 'The Street ',
        highlightText: 'Sneaker ',
        titleSuffix: 'Drop',
        subtitle: 'Trending silhouettes & limited colorways',
        buttonText: 'Explore Drops',
        accentColor: const Color(0xFFEA580C),
        tag: 'EXCLUSIVE',
        tagIcon: Icons.local_fire_department_rounded,
        badgeText: 'TRENDING',
        imageUrl:
            'https://images.unsplash.com/photo-1552346154-21d32810aba3?w=600&q=80',
        onTap: () => onCategorySelected(3),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return SliverToBoxAdapter(
      child: PromoBannerCarousel(
        height: 185.0,
        autoScrollDuration: const Duration(seconds: 4),
        items: _buildBanners(),
      ),
    );
  }
}

/// Shimmer skeleton for category avatars during initial load.
class _HomeCategoriesShimmer extends StatelessWidget {
  final bool isDark;

  const _HomeCategoriesShimmer({required this.isDark});

  @override
  Widget build(BuildContext context) {
    return SliverToBoxAdapter(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  width: 90,
                  height: 16,
                  decoration: BoxDecoration(
                    color: isDark
                        ? const Color(0xFF1E293B)
                        : const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                Container(
                  width: 48,
                  height: 14,
                  decoration: BoxDecoration(
                    color: isDark
                        ? const Color(0xFF1E293B)
                        : const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ],
            ),
          ),
          SizedBox(
            height: 96,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 2),
              itemCount: 6,
              separatorBuilder: (_, _) => const SizedBox(width: 10),
              itemBuilder: (_, _) {
                return Shimmer.fromColors(
                  baseColor: isDark
                      ? const Color(0xFF1E293B)
                      : const Color(0xFFF1F5F9),
                  highlightColor: isDark
                      ? const Color(0xFF334155)
                      : const Color(0xFFFFFFFF),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 54,
                        height: 54,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Container(
                        width: 52,
                        height: 10,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// Horizontal categories rail with clean selection state and 'See all' navigation.
class _HomeCategoriesBar extends StatelessWidget {
  final bool isDark;
  final List<CategoryModel> categories;
  final int selectedCategoryId;
  final ValueChanged<int> onCategorySelected;
  final VoidCallback onSeeAll;

  const _HomeCategoriesBar({
    required this.isDark,
    required this.categories,
    required this.selectedCategoryId,
    required this.onCategorySelected,
    required this.onSeeAll,
  });

  @override
  Widget build(BuildContext context) {
    return SliverToBoxAdapter(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section Title Row
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Categories',
                  style: TextStyle(
                    fontSize: 16.5,
                    fontWeight: FontWeight.w800,
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                  ),
                ),
                GestureDetector(
                  onTap: onSeeAll,
                  behavior: HitTestBehavior.opaque,
                  child: const Padding(
                    padding: EdgeInsets.symmetric(vertical: 4, horizontal: 2),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          'See all',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF2563EB),
                          ),
                        ),
                        SizedBox(width: 3),
                        Icon(
                          Icons.chevron_right_rounded,
                          size: 16,
                          color: Color(0xFF2563EB),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Horizontal Categories List
          SizedBox(
            height: 96,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 2),
              itemCount: categories.length,
              separatorBuilder: (_, _) => const SizedBox(width: 10),
              itemBuilder: (context, index) {
                final category = categories[index];
                final isSelected = selectedCategoryId == category.id;

                return _CategoryCircleItem(
                  category: category,
                  isSelected: isSelected,
                  isDark: isDark,
                  onTap: () => onCategorySelected(category.id),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// Individual circular category item with professional iconography, readable 2-line labels, and smooth tap feedback.
class _CategoryCircleItem extends StatelessWidget {
  final CategoryModel category;
  final bool isSelected;
  final bool isDark;
  final VoidCallback onTap;

  const _CategoryCircleItem({
    required this.category,
    required this.isSelected,
    required this.isDark,
    required this.onTap,
  });

  static IconData _getCategoryIcon(String name, int id) {
    if (id == 0) return Icons.local_fire_department_rounded;
    final lower = name.toLowerCase();
    if (lower.contains('shoe') ||
        lower.contains('sneaker') ||
        lower.contains('footwear')) {
      return Icons.snowshoeing_rounded;
    }
    if (lower.contains('electr') ||
        lower.contains('tech') ||
        lower.contains('gadget') ||
        lower.contains('laptop')) {
      return Icons.devices_rounded;
    }
    if (lower.contains('fashion') ||
        lower.contains('cloth') ||
        lower.contains('apparel') ||
        lower.contains('hoodie')) {
      return Icons.checkroom_rounded;
    }
    if (lower.contains('watch')) {
      return Icons.watch_rounded;
    }
    if (lower.contains('audio') ||
        lower.contains('sound') ||
        lower.contains('headphone')) {
      return Icons.headphones_rounded;
    }
    if (lower.contains('bag') || lower.contains('backpack')) {
      return Icons.backpack_rounded;
    }
    if (lower.contains('game') || lower.contains('gaming')) {
      return Icons.sports_esports_rounded;
    }
    if (lower.contains('beauty') ||
        lower.contains('skincare') ||
        lower.contains('cosmetic')) {
      return Icons.spa_rounded;
    }
    return Icons.category_rounded;
  }

  @override
  Widget build(BuildContext context) {
    return BouncingButton(
      onTap: onTap,
      scaleFactor: 0.94,
      child: SizedBox(
        width: 74,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Circular Category Avatar
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 54,
              height: 54,
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isDark ? const Color(0xFF151D2C) : Colors.white,
                border: Border.all(
                  color: isSelected
                      ? const Color(0xFF2563EB)
                      : (isDark
                          ? const Color(0xFF1E293B)
                          : const Color(0xFFEDF2F7)),
                  width: isSelected ? 2.0 : 0.8,
                ),
                boxShadow: [
                  BoxShadow(
                    color: isSelected
                        ? const Color(0xFF2563EB).withValues(alpha: 0.28)
                        : Colors.black.withValues(
                            alpha: isDark ? 0.18 : 0.035,
                          ),
                    blurRadius: isSelected ? 7 : 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: ClipOval(
                child: category.imageUrl.isNotEmpty
                    ? Image.network(
                        category.imageUrl,
                        fit: BoxFit.cover,
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
                              color: isDark
                                  ? const Color(0xFF1E293B)
                                  : const Color(0xFFF1F5F9),
                            ),
                          );
                        },
                        errorBuilder: (_, _, _) => _fallbackIcon(),
                      )
                    : _fallbackIcon(),
              ),
            ),
            const SizedBox(height: 5),

            // Readable Category Label (2 lines allowed, never truncated awkwardly)
            SizedBox(
              height: 28,
              child: Text(
                category.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 11,
                  height: 1.15,
                  fontWeight: isSelected ? FontWeight.w800 : FontWeight.w600,
                  color: isSelected
                      ? const Color(0xFF2563EB)
                      : (isDark
                          ? Colors.grey.shade300
                          : const Color(0xFF334155)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _fallbackIcon() {
    final iconData = _getCategoryIcon(category.name, category.id);
    return Container(
      decoration: BoxDecoration(
        color: isSelected
            ? const Color(0xFF2563EB).withValues(alpha: isDark ? 0.22 : 0.10)
            : (isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9)),
      ),
      alignment: Alignment.center,
      child: Icon(
        iconData,
        size: 22,
        color: isSelected
            ? const Color(0xFF2563EB)
            : (isDark ? Colors.grey.shade300 : const Color(0xFF475569)),
      ),
    );
  }
}

/// Section header displaying title, count badge, and sort trigger pill.
class _HomeSectionHeader extends StatelessWidget {
  final bool isDark;
  final String title;
  final String subtitle;
  final String? activeSort;
  final VoidCallback? onSortTap;

  const _HomeSectionHeader({
    required this.isDark,
    required this.title,
    required this.subtitle,
    this.activeSort,
    this.onSortTap,
  });

  @override
  Widget build(BuildContext context) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 17.5,
                fontWeight: FontWeight.w800,
                color: isDark ? Colors.white : const Color(0xFF0F172A),
                letterSpacing: -0.4,
              ),
            ),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 7.5,
                    vertical: 2.5,
                  ),
                  decoration: BoxDecoration(
                    color: isDark
                        ? const Color(0xFF1E3A8A).withValues(alpha: 0.3)
                        : const Color(0xFFEFF6FF),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isDark
                          ? const Color(0xFF2563EB).withValues(alpha: 0.5)
                          : const Color(0xFFDBEAFE),
                    ),
                  ),
                  child: Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF2563EB),
                    ),
                  ),
                ),
                if (onSortTap != null) ...[
                  const SizedBox(width: 7),
                  BouncingButton(
                    onTap: onSortTap,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 7.5,
                        vertical: 2.5,
                      ),
                      decoration: BoxDecoration(
                        color: isDark
                            ? const Color(0xFF1E293B)
                            : const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isDark
                              ? const Color(0xFF334155)
                              : const Color(0xFFCBD5E1),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.sort_rounded,
                            size: 13,
                            color: isDark
                                ? Colors.grey.shade300
                                : const Color(0xFF475569),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            activeSort ?? 'Sort',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: isDark
                                  ? Colors.grey.shade300
                                  : const Color(0xFF475569),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Active filter chip rail when filters, search queries, or sort modes are active.
class _HomeActiveFilterBar extends StatelessWidget {
  final bool isDark;
  final String? categoryName;
  final String? searchQuery;
  final String? sortLabel;
  final VoidCallback onClearCategory;
  final VoidCallback onClearSearch;
  final VoidCallback onClearSort;
  final VoidCallback onResetAll;

  const _HomeActiveFilterBar({
    required this.isDark,
    this.categoryName,
    this.searchQuery,
    this.sortLabel,
    required this.onClearCategory,
    required this.onClearSearch,
    required this.onClearSort,
    required this.onResetAll,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            if (categoryName != null)
              _buildFilterChip(
                label: 'Category: $categoryName',
                onClear: onClearCategory,
              ),
            if (searchQuery != null)
              _buildFilterChip(
                label: 'Search: "$searchQuery"',
                onClear: onClearSearch,
              ),
            if (sortLabel != null)
              _buildFilterChip(
                label: 'Sort: $sortLabel',
                onClear: onClearSort,
              ),
            GestureDetector(
              onTap: onResetAll,
              child: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                child: Text(
                  'Clear all',
                  style: TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFFEF4444),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip({
    required String label,
    required VoidCallback onClear,
  }) {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.symmetric(horizontal: 8.5, vertical: 3.5),
      decoration: BoxDecoration(
        color: isDark
            ? const Color(0xFF1E3A8A).withValues(alpha: 0.25)
            : const Color(0xFFEFF6FF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isDark
              ? const Color(0xFF2563EB).withValues(alpha: 0.4)
              : const Color(0xFFBFDBFE),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2563EB),
            ),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: onClear,
            child: const Icon(
              Icons.close_rounded,
              size: 13,
              color: Color(0xFF2563EB),
            ),
          ),
        ],
      ),
    );
  }
}

/// Shimmer skeleton grid during catalog loading.
class _HomeShimmerGrid extends StatelessWidget {
  final bool isDark;

  const _HomeShimmerGrid({required this.isDark});

  @override
  Widget build(BuildContext context) {
    return SliverPadding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
      sliver: SliverGrid(
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          childAspectRatio: 0.64,
          crossAxisSpacing: 14,
          mainAxisSpacing: 14,
        ),
        delegate: SliverChildBuilderDelegate(
          (context, index) {
            return Shimmer.fromColors(
              baseColor: isDark
                  ? const Color(0xFF1E293B)
                  : const Color(0xFFF1F5F9),
              highlightColor: isDark
                  ? const Color(0xFF334155)
                  : const Color(0xFFFFFFFF),
              child: Container(
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF161F30) : Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: isDark
                        ? const Color(0xFF253248)
                        : const Color(0xFFE2E8F0),
                    width: 1.0,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    AspectRatio(
                      aspectRatio: 1.0,
                      child: Container(
                        decoration: const BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.vertical(
                            top: Radius.circular(15),
                          ),
                        ),
                      ),
                    ),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(9, 6, 9, 7),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  width: 44,
                                  height: 14,
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                ),
                                const SizedBox(height: 5),
                                Container(
                                  width: double.infinity,
                                  height: 12,
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                ),
                              ],
                            ),
                            Container(
                              width: 55,
                              height: 16,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(4),
                              ),
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
          childCount: 6,
        ),
      ),
    );
  }
}

/// Error state view when backend is unreachable or network is disconnected.
class _HomeErrorState extends StatelessWidget {
  final bool isDark;
  final String message;
  final VoidCallback onRetry;

  const _HomeErrorState({
    required this.isDark,
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: isDark
                    ? const Color(0xFF7F1D1D).withValues(alpha: 0.25)
                    : const Color(0xFFFEE2E2),
                shape: BoxShape.circle,
                border: Border.all(
                  color: isDark
                      ? const Color(0xFFEF4444).withValues(alpha: 0.3)
                      : const Color(0xFFFECACA),
                  width: 1.5,
                ),
              ),
              child: const Icon(
                Icons.wifi_off_rounded,
                size: 34,
                color: Color(0xFFEF4444),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'Network is not connected',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.3,
                color: isDark ? Colors.white : const Color(0xFF0F172A),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              message.isNotEmpty
                  ? message
                  : 'Unable to connect to the backend server. Please verify your connection or ensure the API is running.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13.5,
                height: 1.4,
                color: isDark
                    ? Colors.grey.shade400
                    : const Color(0xFF64748B),
              ),
            ),
            const SizedBox(height: 20),
            BouncingButton(
              onTap: onRetry,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF2563EB), Color(0xFF1565C0)],
                  ),
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                      blurRadius: 10,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.refresh_rounded, size: 18, color: Colors.white),
                    SizedBox(width: 8),
                    Text(
                      'Retry Connection',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
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
}

/// Responsive 2-column product grid and informative empty search state.
class _HomeProductGrid extends StatelessWidget {
  final bool isDark;
  final List<ProductModel> products;
  final ValueChanged<int> onToggleFavorite;
  final ValueChanged<ProductModel> onAddToCart;
  final VoidCallback? onResetFilters;

  const _HomeProductGrid({
    required this.isDark,
    required this.products,
    required this.onToggleFavorite,
    required this.onAddToCart,
    this.onResetFilters,
  });

  @override
  Widget build(BuildContext context) {
    if (products.isEmpty) {
      return SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: isDark
                        ? const Color(0xFF1E293B)
                        : const Color(0xFFEFF6FF),
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: isDark
                          ? const Color(0xFF334155)
                          : const Color(0xFFDBEAFE),
                      width: 1.5,
                    ),
                  ),
                  child: const Icon(
                    Icons.search_off_rounded,
                    size: 34,
                    color: Color(0xFF2563EB),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'No products found matching your search.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Try checking for spelling errors, using more general terms, or resetting your category filters.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13,
                    color: isDark
                        ? Colors.grey.shade400
                        : const Color(0xFF64748B),
                    height: 1.4,
                  ),
                ),
                if (onResetFilters != null) ...[
                  const SizedBox(height: 20),
                  BouncingButton(
                    onTap: onResetFilters,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 10,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFF2563EB),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFF2563EB).withValues(
                              alpha: 0.3,
                            ),
                            blurRadius: 8,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.refresh_rounded,
                            size: 16,
                            color: Colors.white,
                          ),
                          SizedBox(width: 6),
                          Text(
                            'Reset Filters',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 13.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      );
    }

    return SliverProductGrid(
      products: products,
      childAspectRatio: 0.64,
      heroTagPrefix: 'home-product',
      onTap: (item) {
        Navigator.of(context).push(
          SmoothPageRoute(
            page: ProductDetailScreen(product: item),
          ),
        );
      },
      onToggleFavorite: onToggleFavorite,
      onAddToCart: onAddToCart,
    );
  }
}
