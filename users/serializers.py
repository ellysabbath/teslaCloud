import base64
import logging
import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.enums import UserRole, AccountStatus, VideoType
from users.emails import send_registration_verification_email
from users.models import UserVideo
from verification.models import VerificationToken

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================================
# Base64 helpers
# ============================================================
def split_data_url(data_url: str) -> tuple[str | None, str | None]:
    """'data:video/webm;base64,AAAA' -> ('video/webm', 'AAAA')."""
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        return None, None
    try:
        header, b64 = data_url.split(",", 1)
    except ValueError:
        return None, None
    try:
        mime = header.split(";")[0].replace("data:", "").strip()
    except Exception:
        return None, None
    return mime, b64


def decoded_size(b64: str) -> int:
    """Approximate decoded byte length from base64 length."""
    if not b64:
        return 0
    return (len(b64) * 3) // 4 - b64.count("=")


def validate_base64_payload(data_url: str, kind: str) -> tuple[str, int]:
    """Validate a base64 data URL. No size limit."""
    if not data_url:
        raise serializers.ValidationError(f"{kind} is empty.")

    mime, b64 = split_data_url(data_url)
    if not mime:
        raise serializers.ValidationError(
            f"Invalid {kind} format (expected data URL)."
        )

    try:
        base64.b64decode(b64, validate=True)
    except Exception:
        raise serializers.ValidationError(
            f"{kind.capitalize()} is not valid base64."
        )

    return mime, decoded_size(b64)


def dob_to_date(dob: dict | None) -> date | None:
    if not dob:
        return None
    y, m, d = dob.get("year"), dob.get("month"), dob.get("day")
    if not (y and m and d):
        return None
    try:
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


def generate_next_username() -> str:
    """Return TESLA-<year>-<0001..> using the highest existing sequence."""
    year = timezone.now().year
    prefix = f"TESLA-{year}-"
    last = (
        User.objects.filter(username__startswith=prefix)
        .order_by("-username")
        .values_list("username", flat=True)
        .first()
    )
    next_seq = 1
    if last:
        try:
            next_seq = int(last.replace(prefix, "")) + 1
        except ValueError:
            next_seq = 1
    return f"{prefix}{next_seq:04d}"


# ============================================================
# REGISTRATION
# ============================================================
class RegisterSerializer(serializers.Serializer):
    """Accepts the payload from Register.tsx and creates the user."""
    # Personal
    fullName = serializers.CharField(max_length=150)
    countryCode = serializers.CharField(max_length=5, default="+255")
    mobileNumber = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    currentCity = serializers.CharField(max_length=100, required=False, allow_blank=True)

    # DOB object {year, month, day}
    dateOfBirth = serializers.DictField(required=False)
    educationalBackground = serializers.CharField(required=False, allow_blank=True)

    # Credentials
    password = serializers.CharField(write_only=True, min_length=6)
    confirmPassword = serializers.CharField(write_only=True, min_length=6)
    termsAccepted = serializers.BooleanField()

    # Base64 media
    profilePicture = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    videoRecord = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    # Metadata
    ipAddress = serializers.CharField(required=False, allow_blank=True)
    deviceName = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email is already registered")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmPassword"]:
            raise serializers.ValidationError(
                {"confirmPassword": "Passwords do not match"}
            )
        if not attrs.get("termsAccepted"):
            raise serializers.ValidationError(
                {"termsAccepted": "You must accept the terms"}
            )

        pic = attrs.get("profilePicture")
        if pic:
            mime, size = validate_base64_payload(pic, "Profile picture")
            if not mime.startswith("image/"):
                raise serializers.ValidationError(
                    {"profilePicture": "Must be an image"}
                )
            attrs["_profile_pic_size"] = size

        vid = attrs.get("videoRecord")
        if vid:
            mime, size = validate_base64_payload(vid, "Video recording")
            if not mime.startswith("video/"):
                raise serializers.ValidationError(
                    {"videoRecord": "Must be a video"}
                )
            attrs["_video_size"] = size
            attrs["_video_mime"] = mime

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        dob = dob_to_date(validated_data.get("dateOfBirth") or {})
        pwd = validated_data.pop("password")
        validated_data.pop("confirmPassword", None)
        validated_data.pop("dateOfBirth", None)

        profile_b64 = validated_data.pop("profilePicture", None)
        video_b64 = validated_data.pop("videoRecord", None)
        video_size = validated_data.pop("_video_size", None)
        video_mime = validated_data.pop("_video_mime", None)
        validated_data.pop("_profile_pic_size", None)

        ip = validated_data.pop("ipAddress", None) or None
        device = validated_data.pop("deviceName", None) or None

        user = User(
            username=generate_next_username(),
            email=validated_data["email"],
            full_name=validated_data["fullName"],
            country_code=validated_data.get("countryCode", "+255"),
            mobile_number=validated_data["mobileNumber"],
            region=validated_data.get("region") or None,
            current_city=validated_data.get("currentCity") or None,
            date_of_birth=dob,
            educational_background=validated_data.get("educationalBackground") or None,
            role=UserRole.STUDENT,
            status=AccountStatus.PENDING,
            is_verified=False,
            ip_address=ip,
            device_name=device,
            terms_accepted_at=timezone.now(),
        )
        user.set_password(pwd)

        if profile_b64:
            user.profile_picture_base64 = profile_b64

        user.save()

        if video_b64:
            UserVideo.objects.create(
                user=user,
                video_type=VideoType.REGISTRATION,
                data=video_b64,
                mime_type=video_mime or "video/webm",
                file_size=video_size,
            )

        token = VerificationToken.objects.create(
            user=user,
            token=str(uuid.uuid4()),
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
                "Failed to send verification email to %s", user.email
            )

        return user

    def to_representation(self, user):
        return {
            "id": str(user.id),
            "username": user.username,
            "fullName": user.full_name,
            "email": user.email,
            "countryCode": user.country_code,
            "mobileNumber": user.mobile_number,
            "region": user.region,
            "currentCity": user.current_city,
            "role": user.role,
            "status": user.status,
            "isVerified": user.is_verified,
            "profilePicture": user.profile_picture_base64,
            "createdAt": user.created_at.isoformat(),
        }


# ============================================================
# USER OUTPUT (used by /me/, /login/)
# ============================================================
class UserOutputSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source="full_name")
    countryCode = serializers.CharField(source="country_code")
    mobileNumber = serializers.CharField(source="mobile_number")
    currentCity = serializers.CharField(source="current_city")
    isVerified = serializers.BooleanField(source="is_verified")
    profilePicture = serializers.CharField(
        source="profile_picture_base64", allow_null=True, required=False
    )
    educationalBackground = serializers.CharField(
        source="educational_background", allow_null=True, required=False
    )
    createdAt = serializers.DateTimeField(source="created_at")
    dateOfBirth = serializers.SerializerMethodField()
    registrationVideo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "fullName",
            "email",
            "role",
            "status",
            "isVerified",
            "profilePicture",
            "countryCode",
            "mobileNumber",
            "region",
            "currentCity",
            "dateOfBirth",
            "educationalBackground",
            "createdAt",
            "registrationVideo",
        ]

    def get_dateOfBirth(self, obj):
        if not obj.date_of_birth:
            return None
        return {
            "year": str(obj.date_of_birth.year),
            "month": f"{obj.date_of_birth.month:02d}",
            "day": f"{obj.date_of_birth.day:02d}",
        }

    def get_registrationVideo(self, obj):
        video = obj.latest_registration_video()
        if not video:
            return None
        return {
            "data": video.data,
            "mimeType": video.mime_type,
            "fileSize": video.file_size,
            "durationSec": video.duration_sec,
            "createdAt": video.created_at.isoformat(),
        }


# ============================================================
# LOGIN
# ============================================================
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()  # username OR email
    password = serializers.CharField(write_only=True)
    keepMeLoggedIn = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("username") or not attrs.get("password"):
            raise serializers.ValidationError(
                "Both username and password are required"
            )
        return attrs


# ============================================================
# VERIFY ACCOUNT
# ============================================================
class VerifyTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)


# ============================================================
# RESEND VERIFICATION
# ============================================================
class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


# ============================================================
# PASSWORD RESET — REQUEST (email)
# ============================================================
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


# ============================================================
# PASSWORD RESET — VERIFY (code)
# ============================================================
class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=10)


# ============================================================
# PASSWORD RESET — CONFIRM (new password)
# ============================================================
class PasswordResetConfirmSerializer(serializers.Serializer):
    resetToken = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=6)
    confirmPassword = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmPassword"]:
            raise serializers.ValidationError(
                {"confirmPassword": "Passwords do not match"}
            )
        return attrs



# ============================================================
# Profile update (PATCH /api/auth/me/)
# ============================================================
class ProfileUpdateSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=150, required=False)
    mobileNumber = serializers.CharField(max_length=20, required=False)
    countryCode = serializers.CharField(max_length=5, required=False)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    currentCity = serializers.CharField(max_length=100, required=False, allow_blank=True)
    educationalBackground = serializers.CharField(required=False, allow_blank=True)
    profilePicture = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def update(self, instance, validated_data):
        mapping = {
            "fullName": "full_name",
            "mobileNumber": "mobile_number",
            "countryCode": "country_code",
            "region": "region",
            "currentCity": "current_city",
            "educationalBackground": "educational_background",
        }
        for key, model_field in mapping.items():
            if key in validated_data:
                setattr(instance, model_field, validated_data[key] or None)

        # profilePicture:
        #   - key present, value is a base64 data URL  → set the picture
        #   - key present, value is None or ""         → remove the picture
        #   - key absent                               → leave unchanged
        if "profilePicture" in validated_data:
            pic = validated_data["profilePicture"]

            if pic is None or pic == "":
                instance.profile_picture_base64 = None
            else:
                mime, _ = validate_base64_payload(pic, "Profile picture")
                if not mime.startswith("image/"):
                    raise serializers.ValidationError(
                        {"profilePicture": "Must be an image"}
                    )
                instance.profile_picture_base64 = pic

        instance.save()
        return instance

# ============================================================
# Change password
# ============================================================
class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(write_only=True)
    newPassword = serializers.CharField(write_only=True, min_length=6)
    confirmPassword = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs["newPassword"] != attrs["confirmPassword"]:
            raise serializers.ValidationError(
                {"confirmPassword": "Passwords do not match"}
            )
        return attrs


# ============================================================
# Admin — list users
# ============================================================
class AdminUserRowSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source="full_name")
    phone = serializers.CharField(source="mobile_number")
    countryCode = serializers.CharField(source="country_code")
    currentCity = serializers.CharField(source="current_city", allow_null=True)
    isVerified = serializers.BooleanField(source="is_verified")
    joinedAt = serializers.DateTimeField(source="created_at")
    hasProfilePicture = serializers.SerializerMethodField()
    enrollments = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "fullName",
            "username",
            "email",
            "phone",
            "countryCode",
            "region",
            "currentCity",
            "status",
            "isVerified",
            "enrollments",
            "joinedAt",
            "hasProfilePicture",
        ]

    def get_hasProfilePicture(self, obj):
        return bool(obj.profile_picture_base64)

    def get_enrollments(self, obj):
        try:
            from payments.models import Payment
            return Payment.objects.filter(user=obj, status="paid").count()
        except Exception:
            return 0