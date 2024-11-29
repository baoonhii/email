import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';
import '../constants.dart';
import '../data_classes.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/api_pipeline.dart';

class AccountProvider extends ChangeNotifier {
  Account? _currentAccount;
  String? _sessionToken;
  UserProfile? _userProfile;

  // Getters
  Account? get currentAccount => _currentAccount;
  String? get sessionToken => _sessionToken;
  UserProfile? get userProfile => _userProfile;

  // Method to set the current account
  void setCurrentAccount(Account account) {
    _currentAccount = account;
    print("Set account to $_currentAccount");
    notifyListeners();
  }

  void setUserProfile(UserProfile userProfile) {
    _userProfile = userProfile;
    print("Set user Profile to $_userProfile");
    notifyListeners();
  }

  Future<void> fetchUserProfile() async {
    final responseData = await fetchData(
      url: Uri.parse(API_Endpoints.USER_PROFILE.value),
      method: 'GET',
    );

    final userProfile = UserProfile.fromJson(responseData);
    setUserProfile(userProfile);
  }

  // Method to clear the current account (e.g., on logout)
  void clearCurrentAccount() async {
    _currentAccount = null;
    _sessionToken = null;
    _userProfile = null;

    // Clear stored session token
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('session_token');

    notifyListeners();
  }

  // Optional: Check if an account is currently set
  bool get hasCurrentAccount => _currentAccount != null;

  // Check if session token is valid
  Future<bool> isSessionValid() async {
    final prefs = await SharedPreferences.getInstance();
    final storedToken = prefs.getString('session_token');

    if (storedToken == null) return false;

    try {
      final responseData = await fetchData(
        url: Uri.parse(API_Endpoints.AUTH_VALIDATE_TOKEN.value),
        method: 'POST',
        requiresAuth: false,
        body: {'session_token': storedToken},
      );

      final user = Account.fromJson(responseData['user']);
      setCurrentAccount(user);
      _sessionToken = storedToken;
      return true;
    } catch (e) {
      return false;
    }
  }

  Future<void> login(
    String phoneNumber,
    String password,
    VoidCallback onSuccess,
  ) async {
    final responseData = await fetchData(
      url: Uri.parse(API_Endpoints.AUTH_LOGIN.value),
      method: 'POST',
      requiresAuth: false,
      body: {
        'phone_number': phoneNumber,
        'password': password,
      },
    );

    final user = Account.fromJson(responseData['user']);
    final sessionToken = responseData['session_token'];

    // Store session token
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('session_token', sessionToken);

    setCurrentAccount(user);
    _sessionToken = sessionToken;

    onSuccess();
  }

  Future<void> logout() async {
    try {
      await fetchData(
        url: Uri.parse(API_Endpoints.AUTH_LOGOUT.value),
        method: 'POST',
      );
    } catch (e) {
      print('Logout request failed: $e');
    } finally {
      clearCurrentAccount();
    }
  }

  Future<void> register({
    required String firstName,
    required String lastName,
    required String email,
    required String phoneNumber,
    required String password,
    required String password2,
  }) async {
    await fetchData(
      url: Uri.parse(API_Endpoints.AUTH_REGISTER.value),
      method: 'POST',
      requiresAuth: false,
      body: {
        'username': phoneNumber,
        'first_name': firstName,
        'last_name': lastName,
        'email': email,
        'phone_number': phoneNumber,
        'password': password,
        'password2': password2,
      },
    );
  }

  Future<void> updateProfile({
    required String firstName,
    required String lastName,
    required String email,
    String? bio,
    DateTime? birthdate,
    File? profilePicture,
    Uint8List? profilePictureBytes,
  }) async {
    // Prepare fields
    final fields = {
      'first_name': firstName,
      'last_name': lastName,
      'email': email,
      if (bio != null) 'bio': bio,
      if (birthdate != null)
        'birthdate': DateFormat('yyyy-MM-dd').format(birthdate),
    };

    // Perform file upload or regular update
    final responseData =
        await (profilePicture != null || profilePictureBytes != null
            ? uploadImage(
                url: Uri.parse(API_Endpoints.USER_PROFILE.value),
                fields: fields,
                fileToUpload: profilePicture,
                fileBytes: profilePictureBytes,
                fileFieldName: 'profile_picture',
              )
            : fetchData(
                url: Uri.parse(API_Endpoints.USER_PROFILE.value),
                method: 'PUT',
                body: fields,
              ));

    // Update account and profile
    final updatedUser = Account.fromJson(responseData['user']);
    final updatedProfile = UserProfile.fromJson(
      responseData['user_profile'] ?? responseData,
    );

    setCurrentAccount(updatedUser);
    setUserProfile(updatedProfile);
  }
}
