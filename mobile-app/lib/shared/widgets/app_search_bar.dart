import 'package:flutter/material.dart';

/// Clean, modern search bar widget with customizable border radius,
/// theme-aware neutral surfaces, search icon, and built-in clear action.
class AppSearchBar extends StatefulWidget {
  final TextEditingController? controller;
  final String? initialValue;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final VoidCallback? onClear;
  final VoidCallback? onTap;
  final String hintText;
  final double height;
  final BorderRadiusGeometry borderRadius;
  final EdgeInsetsGeometry? margin;
  final EdgeInsetsGeometry? contentPadding;
  final Color? backgroundColor;
  final Color? borderColor;
  final bool readOnly;
  final bool autofocus;
  final FocusNode? focusNode;
  final Widget? leading;
  final Widget? trailing;
  final bool showClearButton;

  const AppSearchBar({
    super.key,
    this.controller,
    this.initialValue,
    this.onChanged,
    this.onSubmitted,
    this.onClear,
    this.onTap,
    this.hintText = "What's on your list?",
    this.height = 48.0,
    this.borderRadius = const BorderRadius.all(Radius.circular(28)),
    this.margin,
    this.contentPadding,
    this.backgroundColor,
    this.borderColor,
    this.readOnly = false,
    this.autofocus = false,
    this.focusNode,
    this.leading,
    this.trailing,
    this.showClearButton = true,
  });

  @override
  State<AppSearchBar> createState() => _AppSearchBarState();
}

class _AppSearchBarState extends State<AppSearchBar> {
  TextEditingController? _internalController;
  TextEditingController get _effectiveController =>
      widget.controller ??
      (_internalController ??=
          TextEditingController(text: widget.initialValue));

  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _effectiveController.addListener(_handleTextChange);
    _hasText = _effectiveController.text.isNotEmpty;
  }

  @override
  void didUpdateWidget(covariant AppSearchBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.controller != oldWidget.controller) {
      oldWidget.controller?.removeListener(_handleTextChange);
      _effectiveController.addListener(_handleTextChange);
      _hasText = _effectiveController.text.isNotEmpty;
    }
  }

  void _handleTextChange() {
    final hasText = _effectiveController.text.isNotEmpty;
    if (hasText != _hasText) {
      setState(() {
        _hasText = hasText;
      });
    }
  }

  @override
  void dispose() {
    _effectiveController.removeListener(_handleTextChange);
    _internalController?.dispose();
    super.dispose();
  }

  void _handleClear() {
    _effectiveController.clear();
    widget.onChanged?.call('');
    widget.onClear?.call();
    setState(() {
      _hasText = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = widget.backgroundColor ??
        (isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9));
    final border = widget.borderColor ??
        (isDark
            ? const Color(0xFF334155).withValues(alpha: 0.5)
            : const Color(0xFFE2E8F0));
    final textColor = isDark ? Colors.white : const Color(0xFF0F172A);
    final hintColor =
        isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8);
    final iconColor =
        isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B);

    return Container(
      margin: widget.margin,
      constraints: BoxConstraints(minHeight: widget.height),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: widget.borderRadius,
        border: Border.all(color: border, width: 1.0),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.12 : 0.02),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: TextField(
        controller: _effectiveController,
        focusNode: widget.focusNode,
        readOnly: widget.readOnly,
        autofocus: widget.autofocus,
        onTap: widget.onTap,
        onChanged: (val) {
          widget.onChanged?.call(val);
        },
        onSubmitted: widget.onSubmitted,
        textAlignVertical: TextAlignVertical.center,
        style: TextStyle(
          color: textColor,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        decoration: InputDecoration(
          isDense: true,
          hintText: widget.hintText,
          hintStyle: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: hintColor,
          ),
          prefixIcon: widget.leading ??
              Padding(
                padding: const EdgeInsets.only(left: 16, right: 10),
                child: Icon(
                  Icons.search_rounded,
                  size: 21,
                  color: iconColor,
                ),
              ),
          prefixIconConstraints: const BoxConstraints(
            minWidth: 48,
            minHeight: 48,
          ),
          suffixIcon: widget.trailing ??
              (widget.showClearButton && _hasText
                  ? GestureDetector(
                      key: const Key('search_clear_button'),
                      onTap: _handleClear,
                      child: Padding(
                        padding: const EdgeInsets.only(right: 16),
                        child: Icon(
                          Icons.close_rounded,
                          size: 18,
                          color: iconColor,
                        ),
                      ),
                    )
                  : null),
          suffixIconConstraints: const BoxConstraints(
            minWidth: 44,
            minHeight: 44,
          ),
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: widget.contentPadding ??
              const EdgeInsets.symmetric(
                vertical: 12,
                horizontal: 0,
              ),
        ),
      ),
    );
  }
}
