import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:e_commerc_mobile_app/shared/widgets/app_search_bar.dart';

void main() {
  testWidgets('AppSearchBar renders with custom border radius and hint text', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppSearchBar(
            borderRadius: BorderRadius.all(Radius.circular(16)),
            hintText: "What's on your list?",
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Verify hint text and search icon
    expect(find.text("What's on your list?"), findsOneWidget);
    expect(find.byIcon(Icons.search_rounded), findsOneWidget);

    // Verify container has the specified border radius
    final containerFinder = find.descendant(
      of: find.byType(AppSearchBar),
      matching: find.byType(Container),
    );
    expect(containerFinder, findsWidgets);

    final container = tester.widget<Container>(containerFinder.first);
    final boxDecoration = container.decoration as BoxDecoration;
    expect(
      boxDecoration.borderRadius,
      equals(const BorderRadius.all(Radius.circular(16))),
    );
  });

  testWidgets('AppSearchBar typing triggers onChanged and displays clear button', (
    WidgetTester tester,
  ) async {
    String changedValue = '';
    var clearCalled = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AppSearchBar(
            onChanged: (val) => changedValue = val,
            onClear: () => clearCalled = true,
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Initially clear button is hidden
    expect(find.byKey(const Key('search_clear_button')), findsNothing);

    // Enter search text
    await tester.enterText(find.byType(TextField), 'headphones');
    await tester.pumpAndSettle();

    expect(changedValue, equals('headphones'));
    expect(find.byKey(const Key('search_clear_button')), findsOneWidget);

    // Tap clear button
    await tester.tap(find.byKey(const Key('search_clear_button')));
    await tester.pumpAndSettle();

    expect(changedValue, isEmpty);
    expect(clearCalled, isTrue);
    expect(find.byKey(const Key('search_clear_button')), findsNothing);
  });

  testWidgets('AppSearchBar dark mode renders high-contrast theme surfaces', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(),
        home: const Scaffold(
          body: AppSearchBar(),
        ),
      ),
    );

    await tester.pumpAndSettle();

    final containerFinder = find.descendant(
      of: find.byType(AppSearchBar),
      matching: find.byType(Container),
    );
    final container = tester.widget<Container>(containerFinder.first);
    final boxDecoration = container.decoration as BoxDecoration;
    expect(boxDecoration.color, equals(const Color(0xFF1E293B)));
  });

  testWidgets('AppSearchBar submits query via onSubmitted', (
    WidgetTester tester,
  ) async {
    String submittedValue = '';

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AppSearchBar(
            onSubmitted: (val) => submittedValue = val,
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'running shoes');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    expect(submittedValue, equals('running shoes'));
  });
}
