from rest_framework import serializers

from .models import Payment, PaymentMethodInfo


class PaymentMethodInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethodInfo
        fields = [
            "id",
            "name",
            "display_name",
            "lipa_namba",
            "account_number",
            "instructions",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    courseId = serializers.UUIDField(source="course_id", read_only=True)
    courseTitle = serializers.CharField(source="course.title", read_only=True)
    studentName = serializers.CharField(source="user.full_name", read_only=True)
    studentUsername = serializers.CharField(source="user.username", read_only=True)
    submittedAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "courseId",
            "courseTitle",
            "studentName",
            "studentUsername",
            "amount",
            "currency",
            "method",
            "reference",
            "phone_paid_from",
            "status",
            "paid_at",
            "submittedAt",
        ]


class PaymentSubmitSerializer(serializers.Serializer):
    courseId = serializers.UUIDField()
    method = serializers.CharField(max_length=30)
    reference = serializers.CharField(max_length=100)
    phonePaidFrom = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )