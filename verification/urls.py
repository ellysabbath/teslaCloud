from django.urls import path
from .views import VerifyAccountView, ResendVerificationView

app_name = "verification"

urlpatterns = [
    path("verify/", VerifyAccountView.as_view(), name="verify"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend"),
]