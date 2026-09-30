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
    # ---- News ----
    NewsListView,
    NewsDetailView,
    AdminNewsListCreateView,
    AdminNewsDetailView,
)

urlpatterns = [
    # ---------- Notifications ----------
    path("", MyNotificationsView.as_view(), name="notifications-list"),
    path("read-all/", MarkAllNotificationsReadView.as_view(), name="notifications-read-all"),
    path("clear/", ClearNotificationsView.as_view(), name="notifications-clear"),
    path("prefs/", NotificationPrefsView.as_view(), name="notifications-prefs"),
    path("privacy/", PrivacySettingsView.as_view(), name="notifications-privacy"),
    path(
        "admin/broadcast/",
        AdminBroadcastNotificationView.as_view(),
        name="notifications-admin-broadcast",
    ),
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

    # ---------- News ----------
    path("news/", NewsListView.as_view(), name="news-list"),
    path("news/<uuid:news_id>/", NewsDetailView.as_view(), name="news-detail"),

    # ---------- Admin News ----------
    path(
        "admin/news/",
        AdminNewsListCreateView.as_view(),
        name="admin-news-list-create",
    ),
    path(
        "admin/news/<uuid:news_id>/",
        AdminNewsDetailView.as_view(),
        name="admin-news-detail",
    ),
]