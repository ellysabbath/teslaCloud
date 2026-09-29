from django.shortcuts import render

# Create your views here.
# notifications/views.py

"""
Notification, notification-preference and privacy-settings views.

Endpoints
---------
GET    /api/notifications/                     → list my notifications
POST   /api/notifications/<uuid>/read/         → mark one as read
POST   /api/notifications/read-all/            → mark all as read
POST   /api/notifications/<uuid>/delete/       → delete one
POST   /api/notifications/clear/               → delete all

GET    /api/notifications/prefs/               → my notification prefs
PATCH  /api/notifications/prefs/               → update prefs

GET    /api/notifications/privacy/             → my privacy settings
PATCH  /api/notifications/privacy/             → update privacy

POST   /api/notifications/admin/broadcast/     → admin: send to all users
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User  # adjust if your user model lives elsewhere

from .models import (
    Notification,
    UserNotificationPrefs,
    UserPrivacySettings,
)
from .serializers import (
    NotificationSerializer,
    UserNotificationPrefsSerializer,
    UserPrivacySettingsSerializer,
)


def _is_admin(user) -> bool:
    return getattr(user, "role", "") in ("admin", "super-admin")


# ============================================================
# GET /api/notifications/
# ============================================================
class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Notification.objects
            .filter(user=request.user)
            .order_by("-created_at")
        )

        unread_only = (
            request.query_params.get("unread") or ""
        ).strip().lower() == "true"
        if unread_only:
            qs = qs.filter(is_read=False)

        limit = request.query_params.get("limit")
        if limit:
            try:
                qs = qs[: int(limit)]
            except ValueError:
                pass

        data = NotificationSerializer(qs, many=True).data
        unread_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()

        return Response(
            {
                "success": True,
                "data": data,
                "unreadCount": unread_count,
            }
        )


# ============================================================
# POST /api/notifications/<uuid>/read/
# ============================================================
class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notif = get_object_or_404(
            Notification, id=notification_id, user=request.user
        )
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=["is_read", "read_at"])
        return Response(
            {"success": True, "data": NotificationSerializer(notif).data}
        )


# ============================================================
# POST /api/notifications/read-all/
# ============================================================
class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=now)
        return Response({"success": True, "updated": updated})


# ============================================================
# POST /api/notifications/<uuid>/delete/
# ============================================================
class DeleteNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notif = get_object_or_404(
            Notification, id=notification_id, user=request.user
        )
        notif.delete()
        return Response({"success": True})


# ============================================================
# POST /api/notifications/clear/
# ============================================================
class ClearNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        deleted, _ = Notification.objects.filter(
            user=request.user
        ).delete()
        return Response({"success": True, "deleted": deleted})


# ============================================================
# GET / PATCH /api/notifications/prefs/
# ============================================================
class NotificationPrefsView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_or_create(self, user):
        prefs, _ = UserNotificationPrefs.objects.get_or_create(user=user)
        return prefs

    def get(self, request):
        prefs = self._get_or_create(request.user)
        return Response(
            {
                "success": True,
                "data": UserNotificationPrefsSerializer(prefs).data,
            }
        )

    def patch(self, request):
        prefs = self._get_or_create(request.user)
        serializer = UserNotificationPrefsSerializer(
            prefs, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Invalid data",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response({"success": True, "data": serializer.data})


# ============================================================
# GET / PATCH /api/notifications/privacy/
# ============================================================
class PrivacySettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_or_create(self, user):
        prefs, _ = UserPrivacySettings.objects.get_or_create(user=user)
        return prefs

    def get(self, request):
        prefs = self._get_or_create(request.user)
        return Response(
            {
                "success": True,
                "data": UserPrivacySettingsSerializer(prefs).data,
            }
        )

    def patch(self, request):
        prefs = self._get_or_create(request.user)
        serializer = UserPrivacySettingsSerializer(
            prefs, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Invalid data",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response({"success": True, "data": serializer.data})


# ============================================================
# POST /api/notifications/admin/broadcast/
# body: { title, body, type, userId? }  (userId optional → all users)
# ============================================================
class AdminBroadcastNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_admin(request.user):
            return Response(
                {"success": False, "message": "Not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        ntype = (request.data.get("type") or "system").strip()
        user_id = request.data.get("userId")

        if not title:
            return Response(
                {"success": False, "message": "title is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user_id:
            users = User.objects.filter(id=user_id)
            if not users.exists():
                return Response(
                    {"success": False, "message": "User not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            users = User.objects.all()

        created = Notification.objects.bulk_create(
            [
                Notification(
                    user=u,
                    title=title,
                    body=body or None,
                    type=ntype,
                )
                for u in users
            ]
        )

        return Response({"success": True, "created": len(created)})