from rest_framework import serializers

from questions.models import Question, QuestionOption
from .models import (
    ExamAttempt,
    AttemptAnswer,
    AttemptMatchingAnswer,
    AttemptMarkingResult,
)


# ============================================================
# READ — nested inside attempt detail
# ============================================================
class AttemptMarkingResultSerializer(serializers.ModelSerializer):
    questionId = serializers.UUIDField(source="question_id", read_only=True)

    class Meta:
        model = AttemptMarkingResult
        fields = ["id", "questionId", "correct", "awarded", "max_points"]


class AttemptAnswerSerializer(serializers.ModelSerializer):
    questionId = serializers.UUIDField(source="question_id", read_only=True)
    selectedOptionId = serializers.UUIDField(
        source="selected_option_id", read_only=True
    )

    class Meta:
        model = AttemptAnswer
        fields = [
            "id",
            "questionId",
            "selectedOptionId",
            "boolean_answer",
            "text_answer",
            "is_correct",
            "points_awarded",
            "answered_at",
        ]


class AttemptMatchingAnswerSerializer(serializers.ModelSerializer):
    questionId = serializers.UUIDField(source="question_id", read_only=True)
    columnAId = serializers.UUIDField(source="column_a_id", read_only=True)
    columnBId = serializers.UUIDField(
        source="column_b_id", read_only=True, allow_null=True
    )

    class Meta:
        model = AttemptMatchingAnswer
        fields = [
            "id",
            "questionId",
            "columnAId",
            "columnBId",
            "is_correct",
        ]


# ============================================================
# Compact — used by /attempts/mine/ list
# ============================================================
class ExamAttemptSerializer(serializers.ModelSerializer):
    examId = serializers.UUIDField(source="exam_id", read_only=True)
    examTitle = serializers.CharField(source="exam.title", read_only=True)
    courseId = serializers.UUIDField(source="exam.course_id", read_only=True)
    courseTitle = serializers.CharField(
        source="exam.course.title", read_only=True
    )
    studentName = serializers.CharField(source="user.full_name", read_only=True)
    studentUsername = serializers.CharField(
        source="user.username", read_only=True
    )
    durationMinutes = serializers.IntegerField(
        source="exam.duration_minutes", read_only=True
    )

    sessionVideo = serializers.SerializerMethodField()   # ← NEW

    class Meta:
        model = ExamAttempt
        fields = [
            "id", "examId", "examTitle", "courseId", "courseTitle",
            "studentName", "studentUsername",
            "started_at", "submitted_at", "auto_submitted",
            "auto_submit_reason", "durationMinutes",
            "theory_earned", "theory_total", "theory_percent",
            "practical_score", "practical_max", "practical_percent",
            "final_percent", "final_grade", "passed", "status",
            "marked_at", "published_at",
            "sessionVideo",                              # ← NEW
        ]

    def get_sessionVideo(self, obj):
        if obj.session_video and obj.session_video.data:
            return obj.session_video.data
        return None

# ============================================================
# Detail — includes answers + marking
# ============================================================
class ExamAttemptDetailSerializer(ExamAttemptSerializer):
    answers = AttemptAnswerSerializer(many=True, read_only=True)
    matching_answers = AttemptMatchingAnswerSerializer(
        many=True, read_only=True
    )
    marking_results = AttemptMarkingResultSerializer(
        many=True, read_only=True
    )

    class Meta(ExamAttemptSerializer.Meta):
        fields = ExamAttemptSerializer.Meta.fields + [
            "answers",
            "matching_answers",
            "marking_results",
        ]


# ============================================================
# WRITE — submit payload
# ============================================================
class SubmitAnswerSerializer(serializers.Serializer):
    questionId = serializers.UUIDField()
    selectedOptionId = serializers.UUIDField(required=False, allow_null=True)
    booleanAnswer = serializers.BooleanField(required=False, allow_null=True)
    textAnswer = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    matches = serializers.DictField(required=False)  # columnAId -> columnBId


class SubmitAttemptSerializer(serializers.Serializer):
    answers = SubmitAnswerSerializer(many=True)
    autoSubmitted = serializers.BooleanField(default=False)
    autoSubmitReason = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    videoRecord = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )


# ============================================================
# REVIEW — full detail for the admin review modal
# ============================================================
from questions.serializers import QuestionSerializer   # add at top of file
from exams.models import ExamSection, Exam


class AdminAttemptReviewSerializer(serializers.ModelSerializer):
    """
    Returns everything the admin needs to review one attempt:
      - attempt metadata
      - the student's submitted answers
      - the full exam structure (sections + questions + correct answers)
      - the auto-marking results
    """
    examId = serializers.UUIDField(source="exam_id", read_only=True)
    examTitle = serializers.CharField(source="exam.title", read_only=True)
    courseId = serializers.UUIDField(source="exam.course_id", read_only=True)
    courseTitle = serializers.CharField(
        source="exam.course.title", read_only=True
    )
    studentName = serializers.CharField(source="user.full_name", read_only=True)
    studentUsername = serializers.CharField(
        source="user.username", read_only=True
    )
    durationMinutes = serializers.IntegerField(
        source="exam.duration_minutes", read_only=True
    )
    sessionVideo = serializers.SerializerMethodField()

    # Full exam structure for the reviewer
    exam = serializers.SerializerMethodField()

    # Student's answers
    answers = AttemptAnswerSerializer(many=True, read_only=True)
    matching_answers = AttemptMatchingAnswerSerializer(many=True, read_only=True)
    marking_results = AttemptMarkingResultSerializer(many=True, read_only=True)

    class Meta:
        model = ExamAttempt
        fields = [
            "id",
            "examId",
            "examTitle",
            "courseId",
            "courseTitle",
            "studentName",
            "studentUsername",
            "started_at",
            "submitted_at",
            "auto_submitted",
            "auto_submit_reason",
            "durationMinutes",
            "theory_earned",
            "theory_total",
            "theory_percent",
            "practical_score",
            "practical_max",
            "practical_percent",
            "final_percent",
            "final_grade",
            "passed",
            "status",
            "marked_at",
            "published_at",
            "sessionVideo",
            "exam",
            "answers",
            "matching_answers",
            "marking_results",
        ]

    def get_sessionVideo(self, obj):
        if obj.session_video and obj.session_video.data:
            return obj.session_video.data
        return None

    def get_exam(self, obj):
        """
        Return the full exam structure — sections, questions,
        correct answers, and everything else the admin needs
        to grade a submission by hand if required.
        """
        exam = obj.exam
        sections = (
            ExamSection.objects
            .filter(exam=exam)
            .prefetch_related(
                "questions",
                "questions__options",
                "questions__matching_column_a",
                "questions__matching_column_b",
                "questions__matching_scheme",
                "questions__fill_blank_answers",
            )
            .order_by("sort_order")
        )

        return {
            "id": str(exam.id),
            "title": exam.title,
            "year": exam.year,
            "durationMinutes": exam.duration_minutes,
            "sections": [
                {
                    "id": str(section.id),
                    "title": section.title,
                    "kind": section.kind,
                    "instructions": section.instructions,
                    "pointsPerQuestion": float(section.points_per_question),
                    "questions": QuestionSerializer(
                        section.questions.all().order_by("sort_order"),
                        many=True,
                    ).data,
                }
                for section in sections
            ],
        }