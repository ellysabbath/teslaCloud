"""
exams/serializers.py

Serializers for Exam, ExamInstruction, and ExamSection.

Conventions
-----------
* `ExamSerializer` is the READ serializer used by both admin and
  student endpoints. It exposes camelCase field names backed by
  snake_case model fields.
* `ExamWriteSerializer` handles create and update of exam metadata.
  - `courseId` is required on create and optional on partial update.
  - `validate_courseId` runs on every write and rejects unknown ids.
  - `update()` actually reassigns `instance.course`; it never
    silently discards a courseId and never falls back to a default
    course.
* `ExamSectionWriteSerializer` is used by the bulk section upsert
  endpoint. It accepts an optional `id` so the view can tell
  "update existing" apart from "create new".
"""

from rest_framework import serializers

from courses.models import Course

from questions.serializers import QuestionSerializer

from .models import Exam, ExamInstruction, ExamSection


# ============================================================
# INSTRUCTION — read & write
# ============================================================
class ExamInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamInstruction
        fields = ["id", "instruction", "sort_order"]


# ============================================================
# SECTION — read (includes nested questions)
# ============================================================
class ExamSectionSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = ExamSection
        fields = [
            "id",
            "title",
            "kind",
            "instructions",
            "points_per_question",
            "sort_order",
            "questions",
        ]


# ============================================================
# SECTION — write (bulk upsert, no nested questions)
#
# `id` is accepted so the view can match incoming sections against
# existing rows and update them in place. It is never used to set
# the primary key on create — the view strips it before saving.
# ============================================================
class ExamSectionWriteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = ExamSection
        fields = [
            "id",
            "title",
            "kind",
            "instructions",
            "points_per_question",
            "sort_order",
        ]

    def validate_points_per_question(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                "Points must be greater than 0."
            )
        return value


# ============================================================
# EXAM — read
#
# camelCase API surface over snake_case model fields. Used by the
# admin list/detail and by the student-facing exam view.
# ============================================================
class ExamSerializer(serializers.ModelSerializer):
    courseId = serializers.UUIDField(
        source="course_id", read_only=True
    )
    courseTitle = serializers.CharField(
        source="course.title", read_only=True
    )
    durationMinutes = serializers.IntegerField(
        source="duration_minutes", read_only=True
    )
    theoryWeight = serializers.DecimalField(
        source="theory_weight",
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )
    practicalWeight = serializers.DecimalField(
        source="practical_weight",
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )
    passThreshold = serializers.DecimalField(
        source="pass_threshold_pct",
        max_digits=5,
        decimal_places=2,
        read_only=True,
    )
    instructions = ExamInstructionSerializer(
        many=True, read_only=True
    )
    sections = ExamSectionSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "courseId",
            "courseTitle",
            "year",
            "durationMinutes",
            "theoryWeight",
            "practicalWeight",
            "passThreshold",
            "status",
            "published_at",
            "closed_at",
            "created_at",
            "updated_at",
            "instructions",
            "sections",
        ]


# ============================================================
# EXAM — write (create / update metadata)
#
# Notes
# -----
# * On create, `courseId` must be supplied — enforced in create().
# * On partial update, `courseId` is optional. If present, the FK
#   is reassigned. If absent, the existing course is left alone.
# * A missing or unknown `courseId` is a hard 400 — we never fall
#   back to `Course.objects.first()`.
# * The weight check only runs when both weights are present in the
#   payload, so partial updates don't accidentally reset the pair.
# ============================================================
class ExamWriteSerializer(serializers.ModelSerializer):
    courseId = serializers.UUIDField(
        write_only=True,
        required=False,
        allow_null=False,
    )
    durationMinutes = serializers.IntegerField(
        source="duration_minutes", required=False
    )
    theoryWeight = serializers.DecimalField(
        source="theory_weight",
        max_digits=5,
        decimal_places=2,
        required=False,
    )
    practicalWeight = serializers.DecimalField(
        source="practical_weight",
        max_digits=5,
        decimal_places=2,
        required=False,
    )
    passThreshold = serializers.DecimalField(
        source="pass_threshold_pct",
        max_digits=5,
        decimal_places=2,
        required=False,
    )

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "courseId",
            "year",
            "durationMinutes",
            "theoryWeight",
            "practicalWeight",
            "passThreshold",
            "status",
        ]

    # ------------------------------------------------------------
    # Field-level validation
    # ------------------------------------------------------------
    def validate_courseId(self, value):
        if value in (None, ""):
            raise serializers.ValidationError(
                "Course is required."
            )
        if not Course.objects.filter(
            id=value, deleted_at__isnull=True
        ).exists():
            raise serializers.ValidationError("Course not found.")
        return value

    # ------------------------------------------------------------
    # Object-level validation
    #
    # Only enforce the weight rule when BOTH weights are provided.
    # This keeps partial updates (e.g. PATCH {title}) valid without
    # requiring the client to re-send the whole weight pair.
    # ------------------------------------------------------------
    def validate(self, attrs):
        tw = attrs.get("theory_weight")
        pw = attrs.get("practical_weight")

        if tw is not None and pw is not None:
            if float(tw) + float(pw) != 100:
                raise serializers.ValidationError(
                    {
                        "theoryWeight": (
                            "Theory + practical weight must equal 100."
                        )
                    }
                )
        return attrs

    # ------------------------------------------------------------
    # Create
    # ------------------------------------------------------------
    def create(self, validated_data):
        course_id = validated_data.pop("courseId", None)
        if not course_id:
            raise serializers.ValidationError(
                {"courseId": "Course is required when creating an exam."}
            )

        request = self.context.get("request")
        user = (
            request.user
            if request and getattr(request, "user", None) and request.user.is_authenticated
            else None
        )

        return Exam.objects.create(
            course_id=course_id,
            created_by=user,
            **validated_data,
        )

    # ------------------------------------------------------------
    # Update
    #
    # Unlike the previous version, this method does NOT pop and
    # discard `courseId`. If the client sends one, we fetch the
    # Course and reassign the FK. Otherwise we leave the existing
    # course untouched.
    # ------------------------------------------------------------
    def update(self, instance, validated_data):
        course_id = validated_data.pop("courseId", None)

        if course_id:
            try:
                instance.course = Course.objects.get(
                    id=course_id, deleted_at__isnull=True
                )
            except Course.DoesNotExist:
                # validate_courseId already screened this; guard anyway.
                raise serializers.ValidationError(
                    {"courseId": "Course not found."}
                )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance