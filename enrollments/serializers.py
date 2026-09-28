from rest_framework import serializers

from .models import CourseEnrollment


class EnrollmentSerializer(serializers.ModelSerializer):
    courseId = serializers.UUIDField(source="course_id", read_only=True)
    courseTitle = serializers.CharField(source="course.title", read_only=True)
    courseCategory = serializers.CharField(source="course.category", read_only=True)
    courseDescription = serializers.CharField(source="course.description", read_only=True)
    courseDuration = serializers.CharField(source="course.duration", read_only=True)
    courseInstructor = serializers.SerializerMethodField()
    coursePrice = serializers.DecimalField(
        source="course.price", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = CourseEnrollment
        fields = [
            "id",
            "courseId",
            "courseTitle",
            "courseCategory",
            "courseDescription",
            "courseDuration",
            "courseInstructor",
            "coursePrice",
            "enrolled_at",
            "completed_at",
            "progress_pct",
            "status",
        ]

    def get_courseInstructor(self, obj):
        return obj.course.instructor_name or (
            obj.course.instructor.full_name if obj.course.instructor else None
        )