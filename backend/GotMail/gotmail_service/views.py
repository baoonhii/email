from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import Attachment, Email, Label, User, UserProfile, UserSettings
from .serializers import (
    AttachmentSerializer,
    AutoReplySettingsSerializer,
    ChangePasswordSerializer,
    CreateEmailSerializer,
    EmailDetailSerializer,
    EmailSerializer,
    FontSettingsSerializer,
    LabelSerializer,
    LoginSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
    UserSerializer,
    UserSettingsSerializer,
)


class SessionTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        session_token = request.headers.get("Authorization")
        if not session_token:
            return None

        try:
            user = User.objects.get(
                session_token=session_token, session_expiry__gt=timezone.now()
            )
            return (user, None)
        except User.DoesNotExist:
            raise AuthenticationFailed("Invalid or expired token")


# Authentication Views
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                try:
                    validate_phone_number(request.data.get("phone_number"))
                except ValidationError:
                    return Response(
                        {"error": "Invalid phone number format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Check if the phone number already exists
                if User.objects.filter(
                    phone_number=request.data.get("phone_number")
                ).exists():
                    return Response(
                        {"error": "Phone number already registered."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Create user
                user = serializer.save()

                # Create associated profile
                UserProfile.objects.create(user=user)

                # Create default settings
                UserSettings.objects.create(user=user)

                # Create default labels
                default_labels = [
                    {"name": "Important", "color": "#FF0000"},
                    {"name": "Personal", "color": "#00FF00"},
                    {"name": "Work", "color": "#0000FF"},
                ]
                for label_data in default_labels:
                    Label.objects.create(user=user, **label_data)

                # Log in the user
                login(request, user)

                return Response(
                    UserSerializer(user).data, status=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user = serializer.validated_data["user"]

            user.generate_session_token()

            login(request, user)

            return Response(
                {
                    "user": UserSerializer(user).data,
                    "session_token": user.session_token,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            # Try to get the session token from the request
            session_token = request.data.get("session_token") or request.headers.get(
                "Authorization"
            )

            # If token is provided, try to find and invalidate the user's session
            if session_token:
                try:
                    user = User.objects.get(
                        session_token=session_token, session_expiry__gt=timezone.now()
                    )
                    user.session_token = None
                    user.session_expiry = None
                    user.save()
                except User.DoesNotExist:
                    # Token not found or expired, but we'll still proceed with logout
                    pass

            # Perform Django logout
            logout(request)

            return Response(
                {"message": "Successfully logged out."}, status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"message": f"Logout failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ValidateTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_token = request.data.get("session_token")
        try:
            user = User.objects.get(
                session_token=session_token, session_expiry__gt=timezone.now()
            )
            return Response(
                {"user": UserSerializer(user).data, "message": "Token is valid"},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"message": "Invalid or expired token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class UserProfileView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = [SessionTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        # Override get_object to return the profile of the authenticated user
        return get_object_or_404(UserProfile, user=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Allow updating user details along with profile
        user_data = {
            "first_name": request.data.get("first_name"),
            "last_name": request.data.get("last_name"),
            "email": request.data.get("email"),
        }

        # Remove None values
        user_data = {k: v for k, v in user_data.items() if v is not None}

        if user_data:
            user_serializer = UserSerializer(request.user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user_serializer.save()

        # Prepare profile data
        profile_data = {
            "bio": request.data.get("bio"),
            "birthdate": request.data.get("birthdate"),
        }

        # Handle profile picture separately
        if "profile_picture" in request.FILES:
            profile_data["profile_picture"] = request.FILES["profile_picture"]

        # Remove None values
        profile_data = {k: v for k, v in profile_data.items() if v is not None}

        serializer = self.get_serializer(instance, data=profile_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {"user": UserSerializer(request.user).data, "profile": serializer.data}
        )


class AutoReplySettingsView(APIView):
    authentication_classes = [SessionTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Retrieve current auto-reply settings for the authenticated user
        """
        try:
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )
            serializer = AutoReplySettingsSerializer(user_settings)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"error": "Unable to retrieve auto-reply settings", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request):
        """
        Update auto-reply settings for the authenticated user
        """
        try:
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )

            # Validate and update settings
            serializer = AutoReplySettingsSerializer(
                user_settings, data=request.data, partial=True
            )

            if serializer.is_valid():
                # Additional validation for date range
                start_date = serializer.validated_data.get("auto_reply_start_date")
                end_date = serializer.validated_data.get("auto_reply_end_date")

                if start_date and end_date and start_date > end_date:
                    return Response(
                        {"error": "Start date must be before end date"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Save the settings
                serializer.save()
                return Response(serializer.data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": "Unable to update auto-reply settings", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request):
        """
        Toggle auto-reply on/off
        """
        try:
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )

            # Toggle auto-reply status
            user_settings.auto_reply_enabled = not user_settings.auto_reply_enabled

            # If enabling, set default dates if not already set
            if user_settings.auto_reply_enabled:
                if not user_settings.auto_reply_start_date:
                    user_settings.auto_reply_start_date = timezone.now()
                if not user_settings.auto_reply_end_date:
                    user_settings.auto_reply_end_date = (
                        timezone.now() + timezone.timedelta(days=30)
                    )

            user_settings.save()

            serializer = AutoReplySettingsSerializer(user_settings)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": "Unable to toggle auto-reply", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FontSettingsView(APIView):
    authentication_classes = [SessionTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Retrieve current font settings for the authenticated user
        """
        try:
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )
            serializer = FontSettingsSerializer(user_settings)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"error": "Unable to retrieve font settings", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request):
        """
        Update font settings for the authenticated user
        """
        try:
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )

            # Validate and update settings
            serializer = FontSettingsSerializer(
                user_settings, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": "Unable to update font settings", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DarkModeToggleView(APIView):
    authentication_classes = [SessionTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Retrieve current dark mode setting for the authenticated user
        """
        try:
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )
            return Response({"dark_mode": user_settings.dark_mode})
        except Exception as e:
            return Response(
                {"error": "Unable to retrieve dark mode setting", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request):
        """
        Set dark mode setting for the authenticated user based on the provided boolean value
        """
        try:
            print(request)
            user_settings, created = UserSettings.objects.get_or_create(
                user=request.user
            )
            dark_mode = request.data.get("dark_mode")
            print(dark_mode)

            if dark_mode is None:
                return Response(
                    {"error": "dark_mode field is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user_settings.dark_mode = dark_mode
            user_settings.save()

            return Response({"dark_mode": user_settings.dark_mode})
        except Exception as e:
            return Response(
                {"error": "Unable to set dark mode", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SendEmailView(generics.CreateAPIView):
    serializer_class = CreateEmailSerializer
    authentication_classes = [SessionTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.save()

        # Use the EmailSerializer to serialize the created email
        response_serializer = EmailSerializer(email)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


# Advanced Email Views
class AdvancedEmailSearchView(generics.ListAPIView):
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["subject", "body", "sender__phone_number"]

    def get_queryset(self):
        user = self.request.user
        queryset = Email.objects.filter(Q(recipients=user) | Q(sender=user)).exclude(
            is_trashed=True
        )

        # Advanced filtering
        params = self.request.query_params

        # Filter by date range
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        if start_date and end_date:
            queryset = queryset.filter(sent_at__range=[start_date, end_date])

        # Filter by status
        status = params.get("status")
        if status:
            if status == "unread":
                queryset = queryset.filter(is_read=False)
            elif status == "starred":
                queryset = queryset.filter(is_starred=True)

        # Filter by label
        label = params.get("label")
        if label:
            queryset = queryset.filter(labels__name=label)

        # Filter by attachments
        has_attachments = params.get("has_attachments")
        if has_attachments:
            queryset = queryset.filter(attachments__isnull=False).distinct()

        return queryset


# Utility Functions
def validate_phone_number(phone_number):
    """
    Basic phone number validation
    You might want to use a more robust library like phonenumbers
    """
    if not phone_number or len(phone_number) < 10 or len(phone_number) > 15:
        raise ValidationError("Invalid phone number")


def generate_session_token():
    """Generate a unique session token"""
    import uuid

    return str(uuid.uuid4())


# Two-Factor Authentication Setup View
class TwoFactorSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = request.user.profile

        # Generate and send verification code
        verification_code = generate_verification_code()

        # In a real app, you'd send this via SMS
        # For now, we'll just return the code (REMOVE IN PRODUCTION)
        return Response(
            {
                "message": "Verification code generated",
                "verification_code": verification_code,  # REMOVE IN PRODUCTION
            }
        )

    def put(self, request):
        profile = request.user.profile
        code = request.data.get("verification_code")

        # Verify the code (you'd implement actual verification logic)
        if verify_two_factor_code(code):
            profile.two_factor_enabled = True
            profile.save()
            return Response({"message": "Two-factor authentication enabled"})

        return Response(
            {"error": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST
        )


# Placeholder functions - replace with actual implementation
def generate_verification_code():
    import random

    return str(random.randint(100000, 999999))


def verify_two_factor_code(code):
    # Implement actual verification logic
    return len(code) == 6 and code.isdigit()
