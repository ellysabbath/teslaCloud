import logging
import random
import uuid as uuid_lib

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from users.emails import (
    send_password_reset_code_email,
    send_registration_verification_email,
)
from verification.models import VerificationToken

from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    AdminUserRowSerializer,
    UserOutputSerializer,
    VerifyTokenSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================================
# HELPER — first DRF error message
# ============================================================
def _first_error_message(errors: dict) -> str:
    if not errors:
        return "Invalid request"
    first_field = next(iter(errors), None)
    first_error = errors.get(first_field)
    if isinstance(first_error, list) and first_error:
        return str(first_error[0])
    if isinstance(first_error, dict):
        inner = next(iter(first_error.values()), None)
        if isinstance(inner, list) and inner:
            return str(inner[0])
        return str(inner)
    return str(first_error) if first_error else "Invalid request"


# ============================================================
# POST /api/auth/register/
# ============================================================
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": _first_error_message(serializer.errors),
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        return Response(
            {
                "success": True,
                "message": (
                    "Registration successful. We've sent a verification link "
                    "to your email. Please check your inbox."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# POST /api/auth/login/
# ============================================================
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": _first_error_message(ser.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        identifier = ser.validated_data["username"].strip()
        password = ser.validated_data["password"]

        user_obj = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(username=identifier).first()
        )
        if user_obj is None:
            return Response(
                {"success": False, "message": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=user_obj.email, password=password)
        if user is None:
            return Response(
                {"success": False, "message": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.status == "suspended":
            return Response(
                {"success": False, "message": "Your account is suspended"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.is_verified:
            return Response(
                {
                    "success": False,
                    "message": "Please verify your email before logging in",
                    "requiresVerification": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user.last_login_at = timezone.now()
        user.save(update_fields=["last_login_at", "updated_at"])

        refresh = RefreshToken.for_user(user)
        user_data = UserOutputSerializer(user).data
        user_data.pop("registrationVideo", None)

        return Response(
            {
                "success": True,
                "message": "Logged in successfully",
                "data": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


# ============================================================
# GET /api/auth/me/
# ============================================================
# ============================================================
# GET / PATCH /api/auth/me/
# ============================================================
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        include_video = request.query_params.get("include_video") in (
            "1", "true", "yes",
        )
        data = UserOutputSerializer(request.user).data
        if not include_video:
            data.pop("registrationVideo", None)
        return Response({"success": True, "data": data})

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            instance=request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": _first_error_message(serializer.errors),
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()

        data = UserOutputSerializer(request.user).data
        data.pop("registrationVideo", None)

        return Response(
            {
                "success": True,
                "message": "Profile updated successfully.",
                "data": data,
            }
        )


# ============================================================
# POST /api/auth/change-password/
# ============================================================
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {
                    "success": False,
                    "message": _first_error_message(ser.errors),
                    "errors": ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not user.check_password(ser.validated_data["currentPassword"]):
            return Response(
                {"success": False, "message": "Current password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(ser.validated_data["newPassword"])
        user.save(update_fields=["password", "updated_at"])

        return Response(
            {"success": True, "message": "Password updated successfully."}
        )
# ============================================================
# GET /api/auth/me/video/
# ============================================================
class MyRegistrationVideoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        video = request.user.latest_registration_video()
        if not video:
            return Response({"success": True, "data": None})
        return Response(
            {
                "success": True,
                "data": {
                    "data": video.data,
                    "mimeType": video.mime_type,
                    "fileSize": video.file_size,
                    "durationSec": video.duration_sec,
                    "createdAt": video.created_at.isoformat(),
                },
            }
        )


# ============================================================
# POST /api/auth/logout/
# ============================================================
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                pass
        return Response({"success": True, "message": "Logged out"})


# ============================================================
# POST /api/auth/verify/
# ============================================================
class VerifyAccountView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = VerifyTokenSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Verification token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw = ser.validated_data["token"]

        try:
            vt = VerificationToken.objects.select_related("user").get(
                token=raw, purpose="email_verify"
            )
        except VerificationToken.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid or unknown verification token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.used_at:
            return Response(
                {"success": False, "message": "This verification link has already been used"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.expires_at < timezone.now():
            return Response(
                {"success": False, "message": "Verification link has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = vt.user
        user.is_verified = True
        user.email_verified_at = timezone.now()
        if user.status == "pending":
            user.status = "active"
        user.save(
            update_fields=["is_verified", "email_verified_at", "status", "updated_at"]
        )

        vt.used_at = timezone.now()
        vt.save(update_fields=["used_at"])

        return Response(
            {
                "success": True,
                "message": "Account verified successfully",
                "data": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "fullName": user.full_name,
                    "isVerified": user.is_verified,
                    "status": user.status,
                },
            }
        )


# ============================================================
# POST /api/auth/resend-verification/
# ============================================================
class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = ResendVerificationSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Valid email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = ser.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()

        generic_response = {
            "success": True,
            "message": (
                "If that email is registered, a new verification link has been sent."
            ),
        }

        if user is None or user.is_verified:
            return Response(generic_response)

        VerificationToken.objects.filter(
            user=user, purpose="email_verify", used_at__isnull=True
        ).update(used_at=timezone.now())

        token = VerificationToken.objects.create(
            user=user,
            token=str(uuid_lib.uuid4()),
            purpose="email_verify",
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )

        try:
            send_registration_verification_email(
                to_email=user.email,
                full_name=user.full_name,
                username=user.username,
                token=str(token.token),
            )
        except Exception:
            logger.exception(
                "Failed to resend verification email to %s", user.email
            )

        return Response(generic_response)


# ============================================================
# POST /api/auth/password-reset/request/
# ============================================================
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    GENERIC = {
        "success": True,
        "message": (
            "If that email is registered, we've sent a password reset code. "
            "Please check your inbox."
        ),
    }

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "A valid email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = ser.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            return Response(self.GENERIC)

        VerificationToken.objects.filter(
            user=user, purpose="password_reset", used_at__isnull=True
        ).update(used_at=timezone.now())

        code = f"{random.randint(0, 999999):06d}"

        VerificationToken.objects.create(
            user=user,
            token=code,
            purpose="password_reset",
            expires_at=timezone.now() + timezone.timedelta(minutes=15),
        )

        try:
            send_password_reset_code_email(
                to_email=user.email,
                full_name=user.full_name,
                code=code,
            )
        except Exception:
            logger.exception(
                "Failed to send password reset code to %s", user.email
            )

        return Response(self.GENERIC)


# ============================================================
# POST /api/auth/password-reset/verify/
# ============================================================
class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = PasswordResetVerifySerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Email and code are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = ser.validated_data["email"].lower()
        code = ser.validated_data["code"].strip()

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            return Response(
                {"success": False, "message": "Invalid or expired code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vt = (
            VerificationToken.objects
            .filter(user=user, purpose="password_reset", token=code)
            .order_by("-created_at")
            .first()
        )
        if vt is None:
            return Response(
                {"success": False, "message": "Invalid or expired code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.used_at:
            return Response(
                {"success": False, "message": "This code has already been used"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.expires_at < timezone.now():
            return Response(
                {"success": False, "message": "This code has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vt.used_at = timezone.now()
        vt.save(update_fields=["used_at"])

        reset_token_value = str(uuid_lib.uuid4())
        VerificationToken.objects.create(
            user=user,
            token=reset_token_value,
            purpose="password_reset_confirm",
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        return Response(
            {
                "success": True,
                "message": "Code verified. You can now set a new password.",
                "resetToken": reset_token_value,
            }
        )


# ============================================================
# POST /api/auth/password-reset/confirm/
# ============================================================
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {
                    "success": False,
                    "message": _first_error_message(ser.errors),
                    "errors": ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_token = ser.validated_data["resetToken"]
        new_password = ser.validated_data["password"]

        vt = (
            VerificationToken.objects
            .select_related("user")
            .filter(token=reset_token, purpose="password_reset_confirm")
            .first()
        )
        if vt is None:
            return Response(
                {"success": False, "message": "Invalid or unknown reset token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.used_at:
            return Response(
                {"success": False, "message": "This reset link has already been used"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.expires_at < timezone.now():
            return Response(
                {"success": False, "message": "This reset link has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = vt.user
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])

        vt.used_at = timezone.now()
        vt.save(update_fields=["used_at"])

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "success": True,
                "message": "Password reset successful. You are now signed in.",
                "data": UserOutputSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )

# ============================================================
# GET /api/auth/admin/users/
# Returns every registered user with optional filters.
# ============================================================
class AdminUsersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        status_filter = (request.query_params.get("status") or "all").strip().lower()
        page = max(int(request.query_params.get("page", 1) or 1), 1)
        page_size = min(
            max(int(request.query_params.get("page_size", 20) or 20), 1), 100
        )

        qs = User.objects.all().order_by("-created_at")

        if status_filter in ("active", "pending", "suspended"):
            qs = qs.filter(status=status_filter)

        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(full_name__icontains=search)
                | Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(mobile_number__icontains=search)
            )

        total = qs.count()
        start = (page - 1) * page_size
        page_qs = qs[start : start + page_size]

        serializer = AdminUserRowSerializer(page_qs, many=True)

        return Response(
            {
                "success": True,
                "data": serializer.data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }
        )


# ============================================================
# POST /api/auth/admin/users/<user_id>/suspend/
# ============================================================
class AdminSuspendUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.id == request.user.id:
            return Response(
                {"success": False, "message": "You cannot suspend your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.status = "suspended"
        user.is_active = False
        user.save(update_fields=["status", "is_active", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"{user.full_name} has been suspended.",
            }
        )


# ============================================================
# POST /api/auth/admin/users/<user_id>/activate/
# ============================================================
class AdminActivateUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.status = "active"
        user.is_active = True
        user.save(update_fields=["status", "is_active", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"{user.full_name} has been activated.",
            }
        )


# ============================================================
# GET /api/auth/admin/users/<user_id>/
# Full detail: all fields + registration video (base64).
# ============================================================
class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Enrollment count (paid payments)
        try:
            from payments.models import Payment
            enrollments = Payment.objects.filter(user=user, status="paid").count()
        except Exception:
            enrollments = 0

        # Registration video (base64 data URL)
        video = user.latest_registration_video()
        video_payload = None
        if video:
            video_payload = {
                "data": video.data,
                "mimeType": video.mime_type,
                "fileSize": video.file_size,
                "durationSec": video.duration_sec,
                "createdAt": video.created_at.isoformat(),
            }

        return Response(
            {
                "success": True,
                "data": {
                    "id": str(user.id),
                    "username": user.username,
                    "fullName": user.full_name,
                    "email": user.email,
                    "phone": user.mobile_number,
                    "countryCode": user.country_code,
                    "region": user.region,
                    "currentCity": user.current_city,
                    "dateOfBirth": (
                        {
                            "year": str(user.date_of_birth.year),
                            "month": f"{user.date_of_birth.month:02d}",
                            "day": f"{user.date_of_birth.day:02d}",
                        }
                        if user.date_of_birth
                        else None
                    ),
                    "gender": user.gender,
                    "educationalBackground": user.educational_background,
                    "bio": user.bio,
                    "role": user.role,
                    "status": user.status,
                    "isVerified": user.is_verified,
                    "isActive": user.is_active,
                    "emailVerifiedAt": (
                        user.email_verified_at.isoformat()
                        if user.email_verified_at
                        else None
                    ),
                    "lastLoginAt": (
                        user.last_login_at.isoformat() if user.last_login_at else None
                    ),
                    "profilePicture": user.profile_picture_base64,
                    "ipAddress": user.ip_address,
                    "deviceName": user.device_name,
                    "termsAcceptedAt": (
                        user.terms_accepted_at.isoformat()
                        if user.terms_accepted_at
                        else None
                    ),
                    "createdAt": user.created_at.isoformat(),
                    "updatedAt": user.updated_at.isoformat(),
                    "enrollments": enrollments,
                    "registrationVideo": video_payload,
                },
            }
        )




    

# ============================================================
# DELETE /api/auth/admin/users/<user_id>/
# Permanently removes a user and all related rows.
# ============================================================
class AdminDeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.id == request.user.id:
            return Response(
                {"success": False, "message": "You cannot delete your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = user.full_name
        user.delete()

        return Response(
            {"success": True, "message": f"{name} has been deleted."}
        )


# ============================================================
# PATCH /api/auth/admin/users/<user_id>/
# Update arbitrary user fields.
# ============================================================
class AdminUpdateUserView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        return self._update(request, user_id)

    # Frontend sends POST — accept both
    def post(self, request, user_id):
        return self._update(request, user_id)

    def _update(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data or {}

        string_fields = {
            "fullName": "full_name",
            "email": "email",
            "phone": "mobile_number",
            "countryCode": "country_code",
            "region": "region",
            "currentCity": "current_city",
            "educationalBackground": "educational_background",
            "gender": "gender",
            "role": "role",
            "status": "status",
        }

        for key, model_field in string_fields.items():
            if key in data:
                value = data[key]
                if isinstance(value, str):
                    value = value.strip()
                    if value == "":
                        value = None
                setattr(user, model_field, value)

        if "email" in data and data["email"]:
            new_email = data["email"].strip().lower()
            if (
                User.objects.filter(email__iexact=new_email)
                .exclude(id=user.id)
                .exists()
            ):
                return Response(
                    {
                        "success": False,
                        "message": "That email is already registered",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.email = new_email

        if "isVerified" in data:
            user.is_verified = bool(data["isVerified"])
        if "isActive" in data:
            user.is_active = bool(data["isActive"])

        pic = data.get("profilePicture")
        if isinstance(pic, str) and pic.startswith("data:image/"):
            user.profile_picture_base64 = pic

        user.save()

        # Rebuild the full detail payload
        video = user.latest_registration_video()
        video_payload = None
        if video:
            video_payload = {
                "data": video.data,
                "mimeType": video.mime_type,
                "fileSize": video.file_size,
                "durationSec": video.duration_sec,
                "createdAt": video.created_at.isoformat(),
            }

        try:
            from payments.models import Payment
            enrollments = Payment.objects.filter(user=user, status="paid").count()
        except Exception:
            enrollments = 0

        return Response(
            {
                "success": True,
                "message": "User updated successfully.",
                "data": {
                    "id": str(user.id),
                    "username": user.username,
                    "fullName": user.full_name,
                    "email": user.email,
                    "phone": user.mobile_number,
                    "countryCode": user.country_code,
                    "region": user.region,
                    "currentCity": user.current_city,
                    "dateOfBirth": (
                        {
                            "year": str(user.date_of_birth.year),
                            "month": f"{user.date_of_birth.month:02d}",
                            "day": f"{user.date_of_birth.day:02d}",
                        }
                        if user.date_of_birth
                        else None
                    ),
                    "gender": user.gender,
                    "educationalBackground": user.educational_background,
                    "bio": user.bio,
                    "role": user.role,
                    "status": user.status,
                    "isVerified": user.is_verified,
                    "isActive": user.is_active,
                    "emailVerifiedAt": (
                        user.email_verified_at.isoformat()
                        if user.email_verified_at
                        else None
                    ),
                    "lastLoginAt": (
                        user.last_login_at.isoformat() if user.last_login_at else None
                    ),
                    "profilePicture": user.profile_picture_base64,
                    "ipAddress": user.ip_address,
                    "deviceName": user.device_name,
                    "termsAcceptedAt": (
                        user.terms_accepted_at.isoformat()
                        if user.terms_accepted_at
                        else None
                    ),
                    "createdAt": user.created_at.isoformat(),
                    "updatedAt": user.updated_at.isoformat(),
                    "enrollments": enrollments,
                    "registrationVideo": video_payload,
                },
            }
        )