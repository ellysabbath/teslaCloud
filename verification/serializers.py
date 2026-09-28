from rest_framework import serializers


class VerifyTokenSerializer(serializers.Serializer):
    """Input for POST /api/auth/verify/."""
    token = serializers.CharField(max_length=255)


class ResendVerificationSerializer(serializers.Serializer):
    """Input for POST /api/auth/resend-verification/."""
    email = serializers.EmailField()