from django.shortcuts import render

# Create your views here.
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VerificationToken
from .serializers import VerifyTokenSerializer, ResendVerificationSerializer

User = get_user_model()


class VerifyAccountView(APIView):
    """
    POST /api/auth/verify/
    Body: { "token": "<uuid>" }
    Marks the user verified and consumes the token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = VerifyTokenSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Verification token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw = ser.validated_data["token"]

        try:
            vt = VerificationToken.objects.select_related("user").get(
                token=raw, purpose="email_verify"
            )
        except VerificationToken.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid or unknown verification token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.used_at:
            return Response(
                {"success": False, "message": "This verification link has already been used"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vt.expires_at < timezone.now():
            return Response(
                {"success": False, "message": "Verification link has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = vt.user
        user.is_verified = True
        user.email_verified_at = timezone.now()
        if user.status == "pending":
            user.status = "active"
        user.save(update_fields=[
            "is_verified", "email_verified_at", "status", "updated_at",
        ])

        vt.used_at = timezone.now()
        vt.save(update_fields=["used_at"])

        return Response({
            "success": True,
            "message": "Account verified successfully",
            "data": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "fullName": user.full_name,
                "isVerified": user.is_verified,
                "status": user.status,
            },
        })


class ResendVerificationView(APIView):
    """
    POST /api/auth/resend-verification/
    Body: { "email": "..." }
    Issues a fresh token. (In production you would email it.)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = ResendVerificationSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Valid email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = ser.validated_data["email"].lower()
        user = User.objects.filter(email__iexact=email).first()

        # Do not leak whether the email exists
        if user is None or user.is_verified:
            return Response({
                "success": True,
                "message": "If that email exists, a verification link has been sent.",
            })

        # Invalidate any previous unused tokens
        VerificationToken.objects.filter(
            user=user, purpose="email_verify", used_at__isnull=True
        ).update(used_at=timezone.now())

        import uuid as _uuid
        token = VerificationToken.objects.create(
            user=user,
            token=str(_uuid.uuid4()),
            purpose="email_verify",
            expires_at=timezone.now() + timezone.timedelta(days=2),
        )

        return Response({
            "success": True,
            "message": "Verification link sent.",
            # In dev we return the token so the frontend can navigate directly.
            "verifyToken": str(token.token),
        })