import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/utils/validators.dart';
import '../../../shared/widgets/bouncing_button.dart';
import '../providers/auth_provider.dart';

/// Account recovery screen backed by real SMTP / SendGrid password reset endpoints.
class ForgotPasswordScreen extends StatefulWidget {
  final String? initialToken;

  const ForgotPasswordScreen({super.key, this.initialToken});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _requestFormKey = GlobalKey<FormState>();
  final _resetFormKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _tokenController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _tokenStep = false;
  bool _obscurePassword = true;
  String? _statusMessage;

  @override
  void initState() {
    super.initState();
    final initialToken = widget.initialToken?.trim();
    if (initialToken != null && initialToken.isNotEmpty) {
      _tokenController.text = initialToken;
      _tokenStep = true;
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _tokenController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _handleSendResetLink() async {
    if (!(_requestFormKey.currentState?.validate() ?? false)) return;
    final authProvider = context.read<AuthProvider>();
    final result = await authProvider.requestPasswordReset(
      _emailController.text.trim(),
    );
    if (!mounted) return;

    if (result != null) {
      String message =
          result['message']?.toString() ??
          'If an account exists for that email, password reset instructions have been sent.';
      final devResetUrl = result['reset_url']?.toString();
      if (devResetUrl != null && devResetUrl.isNotEmpty) {
        final parsed = Uri.tryParse(devResetUrl);
        final tokenParam = parsed?.queryParameters['token'];
        if (tokenParam != null && tokenParam.isNotEmpty) {
          _tokenController.text = tokenParam;
        }
      }
      setState(() {
        _statusMessage = message;
        _tokenStep = true;
      });
    } else if (authProvider.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(authProvider.errorMessage!),
          backgroundColor: const Color(0xFFEF4444),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  Future<void> _handleConfirmReset() async {
    if (!(_resetFormKey.currentState?.validate() ?? false)) return;
    final authProvider = context.read<AuthProvider>();
    final ok = await authProvider.confirmPasswordReset(
      token: _tokenController.text.trim(),
      newPassword: _newPasswordController.text,
    );
    if (!mounted) return;

    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Password updated successfully. Sign in with your new password.',
          ),
          backgroundColor: Color(0xFF10B981),
          behavior: SnackBarBehavior.floating,
        ),
      );
      Navigator.of(context).pop();
    } else if (authProvider.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(authProvider.errorMessage!),
          backgroundColor: const Color(0xFFEF4444),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final authProvider = context.watch<AuthProvider>();

    return Scaffold(
      backgroundColor: isDark
          ? const Color(0xFF0B1120)
          : const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text('Reset Password'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF2563EB).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.lock_reset_rounded,
                  color: Color(0xFF2563EB),
                  size: 28,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                _tokenStep ? 'Enter Reset Code & Password' : 'Forgot Password?',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                _tokenStep
                    ? 'Paste the single-use reset token from your email and choose a strong new password.'
                    : 'Enter your registered email address to receive a single-use password reset link.',
                style: TextStyle(
                  fontSize: 13.5,
                  height: 1.45,
                  color: isDark
                      ? const Color(0xFF94A3B8)
                      : const Color(0xFF64748B),
                ),
              ),
              if (_statusMessage != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: const Color(0xFF10B981).withValues(alpha: 0.35),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.mark_email_read_outlined,
                        color: Color(0xFF10B981),
                        size: 20,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _statusMessage!,
                          style: TextStyle(
                            fontSize: 12.5,
                            fontWeight: FontWeight.w600,
                            color: isDark
                                ? const Color(0xFFA7F3D0)
                                : const Color(0xFF065F46),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 24),
              if (!_tokenStep)
                Form(
                  key: _requestFormKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextFormField(
                        key: const Key('forgot_password_email_field'),
                        controller: _emailController,
                        keyboardType: TextInputType.emailAddress,
                        validator: Validators.email,
                        decoration: InputDecoration(
                          labelText: 'Email Address',
                          hintText: 'you@example.com',
                          prefixIcon: const Icon(Icons.email_outlined),
                          filled: true,
                          fillColor: isDark
                              ? const Color(0xFF161F30)
                              : Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      BouncingButton(
                        key: const Key('send_reset_link_button'),
                        onTap: authProvider.isLoading
                            ? () {}
                            : _handleSendResetLink,
                        child: Container(
                          height: 52,
                          decoration: BoxDecoration(
                            color: const Color(0xFF2563EB),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          alignment: Alignment.center,
                          child: authProvider.isLoading
                              ? const SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Colors.white,
                                  ),
                                )
                              : const Text(
                                  'Send Reset Instructions',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 15,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextButton(
                        key: const Key('switch_to_token_step_button'),
                        onPressed: () => setState(() => _tokenStep = true),
                        child: const Text('Already have a reset token? Enter it now'),
                      ),
                    ],
                  ),
                )
              else
                Form(
                  key: _resetFormKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextFormField(
                        key: const Key('reset_token_field'),
                        controller: _tokenController,
                        validator: (val) =>
                            (val == null || val.trim().isEmpty)
                            ? 'Enter the reset token from your email'
                            : null,
                        decoration: InputDecoration(
                          labelText: 'Reset Token',
                          hintText: 'Paste token from reset link',
                          prefixIcon: const Icon(Icons.vpn_key_outlined),
                          filled: true,
                          fillColor: isDark
                              ? const Color(0xFF161F30)
                              : Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        key: const Key('new_password_field'),
                        controller: _newPasswordController,
                        obscureText: _obscurePassword,
                        validator: (val) {
                          if (val == null || val.length < 8) {
                            return 'Password must be at least 8 characters';
                          }
                          return null;
                        },
                        decoration: InputDecoration(
                          labelText: 'New Password',
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            onPressed: () => setState(
                              () => _obscurePassword = !_obscurePassword,
                            ),
                            icon: Icon(
                              _obscurePassword
                                  ? Icons.visibility_off_outlined
                                  : Icons.visibility_outlined,
                            ),
                          ),
                          filled: true,
                          fillColor: isDark
                              ? const Color(0xFF161F30)
                              : Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        key: const Key('confirm_new_password_field'),
                        controller: _confirmPasswordController,
                        obscureText: _obscurePassword,
                        validator: (val) {
                          if (val != _newPasswordController.text) {
                            return 'Passwords do not match';
                          }
                          return null;
                        },
                        decoration: InputDecoration(
                          labelText: 'Confirm New Password',
                          prefixIcon: const Icon(Icons.lock_reset_outlined),
                          filled: true,
                          fillColor: isDark
                              ? const Color(0xFF161F30)
                              : Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      BouncingButton(
                        key: const Key('confirm_reset_password_button'),
                        onTap: authProvider.isLoading
                            ? () {}
                            : _handleConfirmReset,
                        child: Container(
                          height: 52,
                          decoration: BoxDecoration(
                            color: const Color(0xFF2563EB),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          alignment: Alignment.center,
                          child: authProvider.isLoading
                              ? const SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Colors.white,
                                  ),
                                )
                              : const Text(
                                  'Update Password',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 15,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: () => setState(() => _tokenStep = false),
                        child: const Text('Need a new email? Request reset again'),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
