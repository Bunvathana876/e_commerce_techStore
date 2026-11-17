import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:e_commerc_mobile_app/core/theme/app_theme.dart';
import 'package:e_commerc_mobile_app/features/notifications/models/notification_model.dart';
import 'package:e_commerc_mobile_app/features/notifications/providers/notification_provider.dart';
import 'package:e_commerc_mobile_app/features/notifications/screens/notifications_screen.dart';
import 'package:e_commerc_mobile_app/features/notifications/widgets/notification_item_card.dart';

void main() {
  group('NotificationModel Unit Tests', () {
    test('parses from standard backend JSON correctly', () {
      final json = {
        'id': 10,
        'user_id': 2,
        'type': 'order',
        'title': 'Order #104 Shipped!',
        'message': 'Your package is on its way.',
        'link': '/orders/104',
        'read': false,
        'created_at': '2026-10-20T07:00:00Z',
      };

      final model = NotificationModel.fromJson(json);

      expect(model.id, 10);
      expect(model.userId, 2);
      expect(model.type, 'order');
      expect(model.title, 'Order #104 Shipped!');
      expect(model.message, 'Your package is on its way.');
      expect(model.read, false);
      expect(model.isUnread, true);
      expect(model.typeLabel, 'Order');
      expect(model.iconData, Icons.shopping_bag_rounded);
    });

    test('generates relative time formatted strings', () {
      final now = DateTime.now();
      final notifRecent = NotificationModel(
        id: 1,
        type: 'promo',
        title: 'Promo',
        message: 'Flash sale',
        read: false,
        createdAt: now.subtract(const Duration(seconds: 10)),
      );
      expect(notifRecent.formattedTime, 'Just now');

      final notifMinutes = NotificationModel(
        id: 2,
        type: 'delivery',
        title: 'Delivery',
        message: 'On way',
        read: true,
        createdAt: now.subtract(const Duration(minutes: 5)),
      );
      expect(notifMinutes.formattedTime, '5m ago');

      final notifHours = NotificationModel(
        id: 3,
        type: 'system',
        title: 'System',
        message: 'Update',
        read: true,
        createdAt: now.subtract(const Duration(hours: 3)),
      );
      expect(notifHours.formattedTime, '3h ago');
    });
  });

  group('NotificationProvider State Tests', () {
    test('filters notifications by category and unread state', () {
      final provider = NotificationProvider();

      expect(provider.notifications.isNotEmpty, true);
      expect(provider.unreadCount > 0, true);

      // Filter by Orders
      provider.setFilter('Orders');
      expect(provider.activeFilter, 'Orders');
      for (final n in provider.filteredNotifications) {
        expect(n.type, 'order');
      }

      // Filter by Unread
      provider.setFilter('Unread');
      expect(provider.activeFilter, 'Unread');
      for (final n in provider.filteredNotifications) {
        expect(n.isUnread, true);
      }

      // Filter by Offers
      provider.setFilter('Offers');
      expect(provider.activeFilter, 'Offers');
      for (final n in provider.filteredNotifications) {
        expect(n.type, 'promo');
      }
    });

    test('markAsRead and markAllAsRead update counts optimistically', () async {
      final provider = NotificationProvider();
      final initialUnread = provider.unreadCount;

      final unreadItem = provider.notifications.firstWhere((n) => !n.read);
      await provider.markAsRead(unreadItem.id);

      expect(provider.notifications.firstWhere((n) => n.id == unreadItem.id).read, true);
      expect(provider.unreadCount, initialUnread - 1);

      await provider.markAllAsRead();
      expect(provider.unreadCount, 0);
      for (final n in provider.notifications) {
        expect(n.read, true);
      }
    });

    test('deleteNotification removes item and clears gracefully', () async {
      final provider = NotificationProvider();
      final totalBefore = provider.notifications.length;
      final firstId = provider.notifications.first.id;

      await provider.deleteNotification(firstId);
      expect(provider.notifications.length, totalBefore - 1);
      expect(provider.notifications.any((n) => n.id == firstId), false);

      await provider.clearAll();
      expect(provider.notifications.isEmpty, true);
      expect(provider.unreadCount, 0);
    });
  });

  group('Notification UI Widget Tests', () {
    testWidgets('NotificationItemCard displays category badge, title, and unread dot', (
      WidgetTester tester,
    ) async {
      final notif = NotificationModel(
        id: 99,
        type: 'delivery',
        title: 'Your order is out for delivery! 🚚',
        message: 'Driver is 5 minutes away from your location.',
        read: false,
        createdAt: DateTime.now().subtract(const Duration(minutes: 10)),
      );

      bool tapped = false;
      bool deleted = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: NotificationItemCard(
              notification: notif,
              isDark: false,
              onTap: () => tapped = true,
              onDelete: () => deleted = true,
            ),
          ),
        ),
      );

      expect(find.text('DELIVERY'), findsOneWidget);
      expect(find.text('Your order is out for delivery! 🚚'), findsOneWidget);
      expect(find.text('Driver is 5 minutes away from your location.'), findsOneWidget);
      expect(find.text('10m ago'), findsOneWidget);

      await tester.tap(find.byType(InkWell));
      expect(tapped, true);
      expect(deleted, false);
    });

    testWidgets('NotificationsScreen renders cleanly and supports tab filtering', (
      WidgetTester tester,
    ) async {
      final provider = NotificationProvider();

      await tester.pumpWidget(
        ChangeNotifierProvider<NotificationProvider>.value(
          value: provider,
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const NotificationsScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Notifications'), findsOneWidget);
      expect(find.textContaining('All ('), findsOneWidget);
      expect(find.textContaining('Unread ('), findsOneWidget);
      expect(find.text('Orders'), findsOneWidget);
      expect(find.text('Offers'), findsOneWidget);

      // Tap on Orders tab
      await tester.tap(find.text('Orders'));
      await tester.pumpAndSettle();

      expect(provider.activeFilter, 'Orders');
    });

    testWidgets('NotificationsScreen renders without overflow on 320px narrow screens', (
      WidgetTester tester,
    ) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final provider = NotificationProvider();

      await tester.pumpWidget(
        ChangeNotifierProvider<NotificationProvider>.value(
          value: provider,
          child: MaterialApp(
            theme: AppTheme.darkTheme,
            home: const NotificationsScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Notifications'), findsOneWidget);
      expect(find.byType(NotificationsScreen), findsOneWidget);
    });

    testWidgets('Tapping delete icon button on NotificationItemCard calls onDelete', (
      WidgetTester tester,
    ) async {
      final notif = NotificationModel(
        id: 77,
        type: 'order',
        title: 'Order Confirmed',
        message: 'Your order has been placed.',
        read: false,
        createdAt: DateTime.now(),
      );

      bool deleted = false;
      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: NotificationItemCard(
              notification: notif,
              isDark: false,
              onTap: () => tapped = true,
              onDelete: () => deleted = true,
            ),
          ),
        ),
      );

      final deleteBtnFinder = find.byKey(const Key('delete_notif_77'));
      expect(deleteBtnFinder, findsOneWidget);

      await tester.tap(deleteBtnFinder);
      await tester.pump();

      expect(deleted, isTrue);
      expect(tapped, isFalse);
    });

    testWidgets('Clearing notifications shows confirmation dialog, removes all items, and allows restore', (
      WidgetTester tester,
    ) async {
      final provider = NotificationProvider();

      await tester.pumpWidget(
        ChangeNotifierProvider<NotificationProvider>.value(
          value: provider,
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const NotificationsScreen(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(provider.notifications.isNotEmpty, isTrue);
      final clearAllButtonFinder = find.byKey(const Key('clear_all_appbar_button'));
      expect(clearAllButtonFinder, findsOneWidget);

      // Tap clear all button in AppBar
      await tester.tap(clearAllButtonFinder);
      await tester.pumpAndSettle();

      // Expect confirmation dialog
      expect(find.text('Clear All Notifications?'), findsOneWidget);
      final confirmBtnFinder = find.byKey(const Key('confirm_clear_all_dialog_button'));
      expect(confirmBtnFinder, findsOneWidget);

      // Confirm clear
      await tester.tap(confirmBtnFinder);
      await tester.pumpAndSettle();

      // Notifications should now be cleared
      expect(provider.notifications.isEmpty, isTrue);
      expect(provider.unreadCount, 0);
      expect(find.text('No notifications yet'), findsOneWidget);

      // Restore notifications button should be visible in empty state
      final restoreBtnFinder = find.text('Restore Sample Notifications');
      expect(restoreBtnFinder, findsOneWidget);

      // Tap restore
      await tester.tap(restoreBtnFinder);
      await tester.pumpAndSettle();

      // Sample notifications should be back
      expect(provider.notifications.isNotEmpty, isTrue);
    });
  });
}

