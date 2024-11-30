import 'package:flutter/material.dart';
import 'package:flutter_email/constants.dart';
import 'package:flutter_gen/gen_l10n/app_localizations.dart';
import 'package:provider/provider.dart';

import '../other_widgets/general.dart';
import '../state_management/account_provider.dart';

class GmailRegisterScreen extends StatefulWidget {
  const GmailRegisterScreen({super.key});

  @override
  State<GmailRegisterScreen> createState() => _GmailRegisterScreenState();
}

class _GmailRegisterScreenState extends State<GmailRegisterScreen> {
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _surnameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmPasswordController =
      TextEditingController();

  final _formKey = GlobalKey<FormState>();
  bool _isLoading = false;

  @override
  void dispose() {
    _nameController.dispose();
    _surnameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.createAccount),
      ),
      body: Center(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32.0),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  getRegistrationTitle(context),
                  const SizedBox(height: 20),
                  getNameField(),
                  const SizedBox(height: 16),
                  getSurnameField(),
                  const SizedBox(height: 16),
                  getPhoneField(),
                  const SizedBox(height: 16),
                  getEmailField(),
                  const SizedBox(height: 16),
                  getPasswordField(context),
                  const SizedBox(height: 16),
                  getConfirmPasswordField(context),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: () {
                      if (_formKey.currentState!.validate()) {
                        final firstName = _nameController.text;
                        final lastName = _surnameController.text;
                        final email = _emailController.text;
                        final phoneNumber = _phoneController.text;
                        final password = _passwordController.text;
                        final password2 = _confirmPasswordController.text;

                        try {
                          setState(() {
                            _isLoading = true;
                          });
                          Provider.of<AccountProvider>(context, listen: false)
                              .register(
                            firstName: firstName,
                            lastName: lastName,
                            email: email,
                            phoneNumber: phoneNumber,
                            password: password,
                            password2: password2,
                          );
                        } catch (e) {
                          showSnackBar(
                            context,
                            'Registration failed: ${e.toString()}',
                          );
                        } finally {
                          setState(() {
                            _isLoading = false;
                          });
                        }

                        Navigator.pushReplacementNamed(
                          context,
                          AuthRoutes.LOGIN.value,
                        );
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      textStyle: const TextStyle(fontSize: 18),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : Text(AppLocalizations.of(context)!.continueNext),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  TextFormField getConfirmPasswordField(BuildContext context) {
    return TextFormField(
      controller: _confirmPasswordController,
      decoration: InputDecoration(
        labelText: AppLocalizations.of(context)!.rePassword,
        border: const OutlineInputBorder(),
      ),
      obscureText: true,
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please confirm your password';
        }
        if (value != _passwordController.text) {
          return 'Passwords do not match';
        }
        return null;
      },
    );
  }

  TextFormField getPasswordField(BuildContext context) {
    return TextFormField(
      controller: _passwordController,
      decoration: InputDecoration(
        labelText: AppLocalizations.of(context)!.password,
        border: const OutlineInputBorder(),
      ),
      obscureText: true,
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your password';
        }
        return null;
      },
    );
  }

  TextFormField getEmailField() {
    return TextFormField(
      controller: _emailController,
      decoration: const InputDecoration(
        labelText: 'Email',
        border: OutlineInputBorder(),
      ),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your email';
        }
        return null;
      },
    );
  }

  TextFormField getPhoneField() {
    return TextFormField(
      controller: _phoneController,
      decoration: const InputDecoration(
        labelText: 'Phone Number',
        border: OutlineInputBorder(),
      ),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your phone number';
        }
        return null;
      },
    );
  }

  TextFormField getSurnameField() {
    return TextFormField(
      controller: _surnameController,
      decoration: const InputDecoration(
        labelText: 'Surname',
        border: OutlineInputBorder(),
      ),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your surname';
        }
        return null;
      },
    );
  }

  TextFormField getNameField() {
    return TextFormField(
      controller: _nameController,
      decoration: const InputDecoration(
        labelText: 'Name',
        border: OutlineInputBorder(),
      ),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Please enter your name';
        }
        return null;
      },
    );
  }

  Text getRegistrationTitle(BuildContext context) {
    return Text(
      AppLocalizations.of(context)!.hello,
      style: const TextStyle(
        fontSize: 24,
        fontWeight: FontWeight.bold,
      ),
      textAlign: TextAlign.center,
    );
  }
}
