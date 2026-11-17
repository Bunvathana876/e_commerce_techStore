import 'package:flutter/material.dart';
import '../../../core/network/api_exceptions.dart';
import '../providers/checkout_provider.dart';

class CheckoutAddressSection extends StatelessWidget {
  final CheckoutProvider checkout;
  const CheckoutAddressSection({super.key, required this.checkout});

  @override
  Widget build(BuildContext context) {
    if (checkout.isLoading) {
      return const Center(
        child: CircularProgressIndicator(
          semanticsLabel: 'Loading delivery addresses',
        ),
      );
    }
    if (!checkout.sessionCurrent || checkout.error != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(checkout.error ?? 'Please sign in to place an order.'),
          TextButton(onPressed: checkout.load, child: const Text('Retry')),
        ],
      );
    }
    final selected = checkout.selectedAddress;
    final disabled = checkout.isSubmitting || checkout.pending != null;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (selected == null)
              const Text(
                'No saved addresses. Add a delivery address to continue.',
              )
            else ...[
              Text(
                selected.recipientName,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(selected.phoneNumber),
              Text(
                [
                      selected.streetAddress,
                      selected.city,
                      selected.province,
                      selected.postalCode,
                    ]
                    .whereType<String>()
                    .where((part) => part.isNotEmpty)
                    .join(', '),
              ),
            ],
            Wrap(
              spacing: 8,
              children: [
                if (checkout.addresses.isNotEmpty)
                  TextButton(
                    key: const Key('change_address_button'),
                    onPressed: disabled ? null : () => _choose(context),
                    child: const Text('Change'),
                  ),
                TextButton.icon(
                  key: const Key('add_address_button'),
                  onPressed: disabled
                      ? null
                      : () => showDialog<void>(
                          context: context,
                          builder: (_) => _AddressForm(checkout: checkout),
                        ),
                  icon: const Icon(Icons.add),
                  label: const Text('Add address'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _choose(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * .7,
          ),
          child: ListView(
            shrinkWrap: true,
            children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Select Delivery Address'),
              ),
              for (final address in checkout.addresses)
                ListTile(
                  key: Key('address_option_${address.id}'),
                  selected: checkout.selectedAddress?.id == address.id,
                  title: Text(address.recipientName),
                  subtitle: Text(address.fullAddress),
                  onTap: () {
                    if (checkout.sessionCurrent) checkout.select(address);
                    Navigator.pop(sheetContext);
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AddressForm extends StatefulWidget {
  final CheckoutProvider checkout;
  const _AddressForm({required this.checkout});
  @override
  State<_AddressForm> createState() => _AddressFormState();
}

class _AddressFormState extends State<_AddressForm> {
  final _form = GlobalKey<FormState>();
  final _fields = {
    'full_name': TextEditingController(),
    'phone': TextEditingController(),
    'address_line': TextEditingController(),
    'city': TextEditingController(),
    'province': TextEditingController(),
    'postal_code': TextEditingController(),
  };
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    for (final controller in _fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.checkout.addAddress({
        for (final entry in _fields.entries) entry.key: entry.value.text.trim(),
        'is_default': widget.checkout.addresses.isEmpty,
      });
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e is ApiException
              ? e.message
              : 'Could not save address. Please retry.';
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    const labels = {
      'full_name': 'Full name',
      'phone': 'Phone number',
      'address_line': 'Street address',
      'city': 'City',
      'province': 'Province (optional)',
      'postal_code': 'Postal code (optional)',
    };
    return AlertDialog(
      title: const Text('Add delivery address'),
      content: SingleChildScrollView(
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final entry in _fields.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: TextFormField(
                    key: Key('address_${entry.key}'),
                    controller: entry.value,
                    enabled: !_saving,
                    decoration: InputDecoration(labelText: labels[entry.key]),
                    keyboardType: entry.key == 'phone'
                        ? TextInputType.phone
                        : TextInputType.streetAddress,
                    textInputAction: TextInputAction.next,
                    validator: (value) =>
                        !['province', 'postal_code'].contains(entry.key) &&
                            (value == null || value.trim().isEmpty)
                        ? 'Required'
                        : null,
                  ),
                ),
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: Text(_saving ? 'Saving…' : 'Save address'),
        ),
      ],
    );
  }
}
