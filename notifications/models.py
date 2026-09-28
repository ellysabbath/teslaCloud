from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=50)  # exam_result | payment | certificate | system
    link_url = models.URLField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"], name="idx_notif_user"),
            models.Index(fields=["user", "is_read"], name="idx_notif_unread"),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.title}"


class UserNotificationPrefs(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="notification_prefs",
    )
    email_news = models.BooleanField(default=True)
    email_courses = models.BooleanField(default=True)
    email_exams = models.BooleanField(default=True)
    email_certificates = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    push_updates = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_notification_prefs"


class UserPrivacySettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="privacy_settings",
    )
    show_profile = models.BooleanField(default=True)
    show_progress = models.BooleanField(default=False)
    show_certificates = models.BooleanField(default=True)
    allow_messages = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_privacy_settings"