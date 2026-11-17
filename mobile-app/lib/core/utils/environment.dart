import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

/// Global flag to detect whether the code is currently running inside `flutter test`.
bool get isFlutterTest {
  if (kIsWeb) return false;
  try {
    return Platform.environment.containsKey('FLUTTER_TEST');
  } catch (_) {
    return false;
  }
}
