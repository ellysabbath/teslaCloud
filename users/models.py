import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

from core.enums import UserRole, AccountStatus, Gender, VideoType
from core.models import TimeStampedModel, SoftDeleteModel


# ============================================================
# Manager
# ============================================================
class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", UserRole.SUPER_ADMIN)
        extra.setdefault("status", AccountStatus.ACTIVE)
        extra.setdefault("is_verified", True)
        return self.create_user(email, username, password, **extra)


# ============================================================
# User
# ============================================================
class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel, SoftDeleteModel):
    # ---------- Identity ----------
    username = models.CharField(max_length=50, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    profile_picture_base64 = models.TextField(blank=True, null=True)

    # ---------- Contact ----------
    country_code = models.CharField(max_length=5, default="+255")
    mobile_number = models.CharField(max_length=20)
    region = models.CharField(max_length=100, blank=True, null=True)
    current_city = models.CharField(max_length=100, blank=True, null=True)

    # ---------- Personal ----------
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=Gender.choices, null=True, blank=True
    )
    educational_background = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    # ---------- Account ----------
    role = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.STUDENT
    )
    status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING,
    )
    is_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    # ---------- Django required ----------
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # ---------- Metadata ----------
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_name = models.CharField(max_length=100, blank=True, null=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "full_name", "mobile_number"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"], name="idx_users_email"),
            models.Index(fields=["username"], name="idx_users_username"),
            models.Index(fields=["role"], name="idx_users_role"),
            models.Index(fields=["status"], name="idx_users_status"),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"

    # ---------- Convenience ----------
    @property
    def is_student(self):
        return self.role == UserRole.STUDENT

    @property
    def is_admin_user(self):
        return self.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    def latest_video(self, video_type: str | None = None):
        """Return the most recent UserVideo for this user (optionally by type)."""
        qs = self.videos.all()
        if video_type:
            qs = qs.filter(video_type=video_type)
        return qs.order_by("-created_at").first()

    def latest_registration_video(self):
        return self.latest_video(VideoType.REGISTRATION)


# ============================================================
# Roles (multi-role support)
# ============================================================
class UserRoleAssignment(TimeStampedModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.CharField(max_length=20, choices=UserRole.choices)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roles_granted",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_roles"
        unique_together = [("user", "role")]
        indexes = [
            models.Index(fields=["user"], name="idx_user_roles_user"),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.role}"


# ============================================================
# Sessions
# ============================================================
class UserSession(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    refresh_token = models.TextField(unique=True)
    device_name = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_sessions"
        indexes = [
            models.Index(fields=["user"], name="idx_sessions_user"),
            models.Index(fields=["refresh_token"], name="idx_sessions_token"),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.device_name or 'unknown device'}"


# ============================================================
# Videos (base64 data URLs in the DB)
# ============================================================
class UserVideo(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="videos")
    video_type = models.CharField(max_length=30, choices=VideoType.choices)

    # Base64 data URL: "data:video/webm;base64,AAAA..."
    data = models.TextField()

    mime_type = models.CharField(max_length=50, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)  # bytes of decoded payload
    duration_sec = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "user_videos"
        indexes = [
            models.Index(fields=["user"], name="idx_user_videos_user"),
            models.Index(fields=["user", "video_type"], name="idx_user_videos_type"),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.video_type} ({self.file_size or 0} B)"