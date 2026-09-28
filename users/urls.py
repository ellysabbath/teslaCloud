from django.urls import path

from .views import (
    AdminActivateUserView,
    AdminSuspendUserView,
    AdminUserDetailView,
    AdminUsersListView,
    ChangePasswordView,
    LoginView,
    AdminUpdateUserView,
    LogoutView,
    AdminDeleteUserView,
    MeView,
    MyRegistrationVideoView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    RegisterView,
    ResendVerificationView,
    VerifyAccountView,
)

app_name = "users"

urlpatterns = [
    # Registration + verification
    path("register/", RegisterView.as_view(), name="register"),
    path("verify/", VerifyAccountView.as_view(), name="verify"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),

    # Auth
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # Current user
    path("me/", MeView.as_view(), name="me"),
    path("me/video/", MyRegistrationVideoView.as_view(), name="me-video"),
    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),

    # Password reset
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/verify/",
        PasswordResetVerifyView.as_view(),
        name="password-reset-verify",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),

    # Admin — users
    path(
        "admin/users/",
        AdminUsersListView.as_view(),
        name="admin-users",
    ),
    path(
        "admin/users/<uuid:user_id>/",
        AdminUserDetailView.as_view(),
        name="admin-user-detail",
    ),
    path(
        "admin/users/<uuid:user_id>/suspend/",
        AdminSuspendUserView.as_view(),
        name="admin-user-suspend",
    ),
    path(
        "admin/users/<uuid:user_id>/activate/",
        AdminActivateUserView.as_view(),
        name="admin-user-activate",
    ),

        path(
        "admin/users/<uuid:user_id>/",
        AdminUserDetailView.as_view(),
        name="admin-user-detail",
    ),
    path(
        "admin/users/<uuid:user_id>/update/",
        AdminUpdateUserView.as_view(),
        name="admin-user-update",
    ),
    path(
        "admin/users/<uuid:user_id>/delete/",
        AdminDeleteUserView.as_view(),
        name="admin-user-delete",
    ),
]