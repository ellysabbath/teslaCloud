# notifications/serializers.py

from rest_framework import serializers

from .models import (
    Notification,
    UserNotificationPrefs,
    UserPrivacySettings,
)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "type",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class UserNotificationPrefsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotificationPrefs
        fields = [
            "email_news",
            "email_courses",
            "email_exams",
            "email_certificates",
            "sms_alerts",
            "push_updates",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class UserPrivacySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPrivacySettings
        fields = [
            "show_profile",
            "show_progress",
            "show_certificates",
            "allow_messages",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]