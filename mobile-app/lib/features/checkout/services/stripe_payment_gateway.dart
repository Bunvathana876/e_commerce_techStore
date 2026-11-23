import 'package:flutter_stripe/flutter_stripe.dart';

/// Thrown when the Stripe PaymentSheet fails or is dismissed before completion.
class StripePaymentSheetException implements Exception {
  final String message;
  final bool cancelled;

  const StripePaymentSheetException(this.message, {this.cancelled = false});

  @override
  String toString() => message;
}

/// Result returned by backend card PaymentIntent initialization.
class CardPaymentIntentSession {
  final int paymentId;
  final String transactionRef;
  final int orderId;
  final String paymentIntentId;
  final String clientSecret;
  final double amount;
  final String currency;
  final String publishableKey;

  const CardPaymentIntentSession({
    required this.paymentId,
    required this.transactionRef,
    required this.orderId,
    required this.paymentIntentId,
    required this.clientSecret,
    required this.amount,
    required this.currency,
    required this.publishableKey,
  });

  factory CardPaymentIntentSession.fromJson(Map<String, dynamic> json) {
    final amountRaw = json['amount'];
    final parsedAmount = amountRaw is num
        ? amountRaw.toDouble()
        : double.tryParse('$amountRaw') ?? 0.0;
    return CardPaymentIntentSession(
      paymentId: (json['payment_id'] as num?)?.toInt() ?? 0,
      transactionRef: json['transaction_ref']?.toString() ?? '',
      orderId: (json['order_id'] as num?)?.toInt() ?? 0,
      paymentIntentId: json['payment_intent_id']?.toString() ?? '',
      clientSecret: json['client_secret']?.toString() ?? '',
      amount: parsedAmount,
      currency: (json['currency']?.toString() ?? 'usd').toLowerCase(),
      publishableKey: json['publishable_key']?.toString() ?? '',
    );
  }
}

/// Abstraction over flutter_stripe PaymentSheet so checkout flows can be tested deterministically.
abstract class StripePaymentGateway {
  Future<void> presentCardPaymentSheet({
    required String publishableKey,
    required String clientSecret,
    String merchantDisplayName = 'Blue Panda',
    bool? isDarkTheme,
  });
}

class FlutterStripePaymentGateway implements StripePaymentGateway {
  const FlutterStripePaymentGateway();

  @override
  Future<void> presentCardPaymentSheet({
    required String publishableKey,
    required String clientSecret,
    String merchantDisplayName = 'Blue Panda',
    bool? isDarkTheme,
  }) async {
    if (publishableKey.trim().isEmpty || clientSecret.trim().isEmpty) {
      throw const StripePaymentSheetException(
        'Stripe payment session is incomplete. Please try again.',
      );
    }

    if (Stripe.publishableKey != publishableKey) {
      Stripe.publishableKey = publishableKey;
      await Stripe.instance.applySettings();
    }

    await Stripe.instance.initPaymentSheet(
      paymentSheetParameters: SetupPaymentSheetParameters(
        paymentIntentClientSecret: clientSecret,
        merchantDisplayName: merchantDisplayName,
      ),
    );

    try {
      await Stripe.instance.presentPaymentSheet();
    } on StripeException catch (error) {
      final cancelled = error.error.code == FailureCode.Canceled;
      final message = cancelled
          ? 'Card payment was cancelled. Your order awaits payment confirmation.'
          : (error.error.localizedMessage ??
                error.error.message ??
                'Card payment could not be completed.');
      throw StripePaymentSheetException(message, cancelled: cancelled);
    }
  }
}
