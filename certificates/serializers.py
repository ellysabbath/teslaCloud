# certificates/serializers.py

from rest_framework import serializers

from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    courseId = serializers.UUIDField(source="course_id", read_only=True)
    courseTitle = serializers.CharField(source="course.title", read_only=True)
    studentName = serializers.CharField(source="user.full_name", read_only=True)
    studentUsername = serializers.CharField(
        source="user.username", read_only=True
    )

    class Meta:
        model = Certificate
        fields = [
            "id",
            "certificate_number",
            "courseId",
            "courseTitle",
            "studentName",
            "studentUsername",
            "grade",
            "final_percentage",
            "verification_url",
            "image_data_url",
            "image_watermarked_data_url",
            "status",
            "is_published",
            "issued_at",
            "revoked_at",
            "revoke_reason",
        ]
        read_only_fields = fields


class CertificateIssueSerializer(serializers.Serializer):
    userId = serializers.UUIDField()
    courseId = serializers.UUIDField()
    grade = serializers.CharField(required=False, allow_blank=True)
    finalPercentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )