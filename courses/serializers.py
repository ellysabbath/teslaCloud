from rest_framework import serializers

from .models import Course, CourseLearningOutcome


# ============================================================
# Learning outcome
# ============================================================
class CourseLearningOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseLearningOutcome
        fields = ["id", "outcome", "sort_order"]


# ============================================================
# Read serializer (used in lists and detail)
# ============================================================
class CourseSerializer(serializers.ModelSerializer):
    learning_outcomes = CourseLearningOutcomeSerializer(many=True, read_only=True)

    # Frontend field names (camelCase) — map from model snake_case
    fullDescription = serializers.CharField(source="full_description", allow_null=True, required=False)
    whyLearn = serializers.CharField(source="why_learn", allow_null=True, required=False)
    whatWillLearn = serializers.SerializerMethodField()
    practicals = serializers.IntegerField(source="practicals_count", required=False)
    theoryDays = serializers.CharField(source="theory_days", allow_null=True, required=False)
    practicalDays = serializers.CharField(source="practical_days", allow_null=True, required=False)
    theoryExam = serializers.CharField(source="theory_exam", allow_null=True, required=False)
    practicalExam = serializers.CharField(source="practical_exam", allow_null=True, required=False)
    image = serializers.CharField(source="image_url", allow_null=True, required=False)
    instructor = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    instructorId = serializers.UUIDField(source="instructor_id", read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "fullDescription",
            "whyLearn",
            "whatWillLearn",
            "category",
            "price",
            "currency",
            "duration",
            "practicals",
            "theoryDays",
            "practicalDays",
            "theoryExam",
            "practicalExam",
            "image",
            "instructor",
            "instructorId",
            "instructor_name",
            "status",
            "created_at",
            "updated_at",
            "learning_outcomes",
        ]

    def get_whatWillLearn(self, obj):
        return [o.outcome for o in obj.learning_outcomes.all().order_by("sort_order")]


# ============================================================
# Write serializer (create / update)
# ============================================================
class CourseWriteSerializer(serializers.ModelSerializer):
    # Accept camelCase from the frontend
    fullDescription = serializers.CharField(source="full_description", required=False, allow_null=True, allow_blank=True)
    whyLearn = serializers.CharField(source="why_learn", required=False, allow_null=True, allow_blank=True)
    whatWillLearn = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        write_only=True,
    )
    practicals = serializers.IntegerField(source="practicals_count", required=False)
    theoryDays = serializers.CharField(source="theory_days", required=False, allow_blank=True, allow_null=True)
    practicalDays = serializers.CharField(source="practical_days", required=False, allow_blank=True, allow_null=True)
    theoryExam = serializers.CharField(source="theory_exam", required=False, allow_blank=True, allow_null=True)
    practicalExam = serializers.CharField(source="practical_exam", required=False, allow_blank=True, allow_null=True)
    image = serializers.CharField(source="image_url", required=False, allow_blank=True, allow_null=True)
    instructor = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "fullDescription",
            "whyLearn",
            "whatWillLearn",
            "category",
            "price",
            "currency",
            "duration",
            "practicals",
            "theoryDays",
            "practicalDays",
            "theoryExam",
            "practicalExam",
            "image",
            "instructor",
            "instructor_name",
            "status",
        ]

    def validate_price(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("Price must be zero or greater")
        return value

    def _save_outcomes(self, course, items):
        if items is None:
            return
        # Replace all outcomes
        course.learning_outcomes.all().delete()
        cleaned = [s.strip() for s in items if isinstance(s, str) and s.strip()]
        for idx, text in enumerate(cleaned):
            CourseLearningOutcome.objects.create(
                course=course, outcome=text, sort_order=idx
            )

    def create(self, validated_data):
        outcomes = validated_data.pop("whatWillLearn", None)
        # `instructor` is a free-text name — store it on `instructor_name`
        instructor_name = validated_data.pop("instructor", None)
        if instructor_name and not validated_data.get("instructor_name"):
            validated_data["instructor_name"] = instructor_name

        course = Course.objects.create(**validated_data)
        self._save_outcomes(course, outcomes)
        return course

    def update(self, instance, validated_data):
        outcomes = validated_data.pop("whatWillLearn", None)
        instructor_name = validated_data.pop("instructor", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if instructor_name is not None:
            instance.instructor_name = instructor_name

        instance.save()
        self._save_outcomes(instance, outcomes)
        return instance