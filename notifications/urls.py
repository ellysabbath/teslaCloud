# notifications/urls.py

from django.urls import path

from .views import (
    MyNotificationsView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
    DeleteNotificationView,
    ClearNotificationsView,
    NotificationPrefsView,
    PrivacySettingsView,
    AdminBroadcastNotificationView,
)

urlpatterns = [
    # List
    path("", MyNotificationsView.as_view(), name="notifications-list"),

    # Bulk actions (must come before <uuid> routes)
    path(
        "read-all/",
        MarkAllNotificationsReadView.as_view(),
        name="notifications-read-all",
    ),
    path(
        "clear/",
        ClearNotificationsView.as_view(),
        name="notifications-clear",
    ),

    # Preferences + privacy
    path(
        "prefs/",
        NotificationPrefsView.as_view(),
        name="notifications-prefs",
    ),
    path(
        "privacy/",
        PrivacySettingsView.as_view(),
        name="notifications-privacy",
    ),

    # Admin broadcast
    path(
        "admin/broadcast/",
        AdminBroadcastNotificationView.as_view(),
        name="notifications-admin-broadcast",
    ),

    # Single-item actions
    path(
        "<uuid:notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="notifications-mark-read",
    ),
    path(
        "<uuid:notification_id>/delete/",
        DeleteNotificationView.as_view(),
        name="notifications-delete",
    ),
]