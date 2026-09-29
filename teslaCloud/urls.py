from django.contrib import admin
from django.urls import path, include

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # ============================================================
    # Django admin
    # ============================================================
    path("admin/", admin.site.urls),

    # ============================================================
    # Auth (register, verify, login, logout, me, me/video,
    # password-reset/*, admin users)
    # ============================================================
    path("api/auth/", include("users.urls")),

    # ============================================================
    # Domain APIs
    # ============================================================
    path("api/courses/", include("courses.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/enrollments/", include("enrollments.urls")),
    path("api/exams/", include("exams.urls")),
    path("api/attempts/", include("attempts.urls")),
    path("api/exams/", include("questions.urls")),
    path("api/certificates/", include("certificates.urls")),
    path("api/notifications/", include("notifications.urls")),

    # ============================================================
    # JWT refresh — lives under /api/auth/ so the frontend
    # can hit `POST /api/auth/token/refresh/` with the stored
    # refresh token to renew the access token silently.
    # ============================================================
    path(
        "api/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
]