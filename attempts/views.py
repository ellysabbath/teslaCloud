from django.shortcuts import render
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exams.models import Exam
from questions.models import (
    Question,
    QuestionOption,
    QuestionBooleanAnswer,
    MatchingScheme,
    FillBlankAnswer,
)

from .models import (
    ExamAttempt,
    AttemptAnswer,
    AttemptMatchingAnswer,
    AttemptMarkingResult,
)
from .serializers import (
    ExamAttemptSerializer,
    ExamAttemptDetailSerializer,
    SubmitAttemptSerializer,
    AdminAttemptReviewSerializer,
)


# ============================================================
# HELPER — auto-mark one attempt
# ============================================================
def _auto_mark(attempt: ExamAttempt) -> None:
    """
    Grade theory-only questions and populate:
      - AttemptMarkingResult rows
      - attempt.theory_earned / theory_total / theory_percent
      - attempt.status (stays 'pending' until admin marks practical)
    """
    total_points = 0.0
    earned_points = 0.0

    # Clear any previous marking rows (safe on re-run)
    attempt.marking_results.all().delete()

    sections = attempt.exam.sections.all().prefetch_related("questions")

    for section in sections:
        pts_per_q = float(section.points_per_question or 0)
        for question in section.questions.all():
            total_points += pts_per_q
            answer = attempt.answers.filter(question=question).first()
            is_correct = False

            if answer:
                if question.type == "multiple-choice":
                    if (
                        answer.selected_option
                        and answer.selected_option.is_correct
                    ):
                        is_correct = True

                elif question.type == "true-false":
                    try:
                        correct = question.boolean_answer.correct_value
                        is_correct = answer.boolean_answer == correct
                    except QuestionBooleanAnswer.DoesNotExist:
                        pass

                elif question.type == "matching":
                    expected = {
                        str(row.column_a_id): str(row.column_b_id)
                        for row in question.matching_scheme.all()
                    }
                    given = {
                        str(m.column_a_id): str(m.column_b_id)
                        if m.column_b_id
                        else ""
                        for m in attempt.matching_answers.filter(
                            question=question
                        )
                    }
                    if expected and expected == given:
                        is_correct = True

                elif question.type == "fill-blank":
                    accepted = [
                        a.answer_text.strip().lower()
                        for a in question.fill_blank_answers.all()
                    ]
                    given = (answer.text_answer or "").strip().lower()
                    if given and given in accepted:
                        is_correct = True

            awarded = pts_per_q if is_correct else 0.0
            earned_points += awarded

            AttemptMarkingResult.objects.create(
                attempt=attempt,
                question=question,
                correct=is_correct,
                awarded=awarded,
                max_points=pts_per_q,
            )

    theory_percent = (
        (earned_points / total_points) * 100 if total_points > 0 else 0
    )

    attempt.theory_earned = earned_points
    attempt.theory_total = total_points
    attempt.theory_percent = round(theory_percent, 2)
    attempt.save(
        update_fields=[
            "theory_earned",
            "theory_total",
            "theory_percent",
            "updated_at",
        ]
    )


# ============================================================
# POST /api/attempts/start/<exam_id>/
# ============================================================
class StartAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id, deleted_at__isnull=True)
        except Exam.DoesNotExist:
            return Response(
                {"success": False, "message": "Exam not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if exam.status != "published":
            return Response(
                {"success": False, "message": "This exam is not available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = ExamAttempt.objects.filter(
            exam=exam, user=request.user
        ).first()
        if existing:
            return Response(
                {
                    "success": True,
                    "message": "Attempt already exists",
                    "data": ExamAttemptSerializer(existing).data,
                }
            )

        attempt = ExamAttempt.objects.create(exam=exam, user=request.user)

        return Response(
            {
                "success": True,
                "message": "Attempt started",
                "data": ExamAttemptSerializer(attempt).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# POST /api/attempts/<attempt_id>/submit/
# ============================================================
class SubmitAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(
                id=attempt_id, user=request.user
            )
        except ExamAttempt.DoesNotExist:
            return Response(
                {"success": False, "message": "Attempt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attempt.submitted_at:
            return Response(
                {
                    "success": False,
                    "message": "This attempt was already submitted.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = SubmitAttemptSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Invalid submission",
                    "errors": ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------- Save answers ----------
        attempt.answers.all().delete()
        attempt.matching_answers.all().delete()

        for raw in ser.validated_data["answers"]:
            qid = raw["questionId"]
            try:
                question = Question.objects.get(id=qid)
            except Question.DoesNotExist:
                continue

            # Non-matching types
            if question.type in (
                "multiple-choice",
                "true-false",
                "fill-blank",
            ):
                AttemptAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_option_id=raw.get("selectedOptionId"),
                    boolean_answer=raw.get("booleanAnswer"),
                    text_answer=raw.get("textAnswer") or None,
                )

            # Matching
            elif question.type == "matching":
                matches = raw.get("matches") or {}
                for a_id, b_id in matches.items():
                    AttemptMatchingAnswer.objects.create(
                        attempt=attempt,
                        question=question,
                        column_a_id=a_id,
                        column_b_id=b_id or None,
                    )

        # ---------- Save the recorded video (base64) ----------
        video_b64 = ser.validated_data.get("videoRecord")

        if video_b64:
            from users.models import UserVideo
            from core.enums import VideoType

            user_video = UserVideo.objects.create(
                user=request.user,
                video_type=VideoType.EXAM_SESSION,
                data=video_b64,
                mime_type="video/webm",
                file_size=len(video_b64) * 3 // 4,   # approx decoded size
            )
            # Link the video to this attempt so it can be retrieved later
            attempt.session_video = user_video

        # ---------- Timestamps ----------
        attempt.submitted_at = timezone.now()
        attempt.auto_submitted = ser.validated_data.get(
            "autoSubmitted", False
        )
        attempt.auto_submit_reason = (
            ser.validated_data.get("autoSubmitReason") or None
        )
        attempt.save(
            update_fields=[
                "submitted_at",
                "auto_submitted",
                "auto_submit_reason",
                "session_video",          # ← persist the FK
                "updated_at",
            ]
        )

        # ---------- Auto-mark theory ----------
        _auto_mark(attempt)

        # Refresh so the serializer picks up the linked video
        attempt.refresh_from_db()

        return Response(
            {
                "success": True,
                "message": "Attempt submitted",
                "data": ExamAttemptDetailSerializer(attempt).data,
            }
        )


# ============================================================
# GET /api/attempts/mine/
# ============================================================
class MyAttemptsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            ExamAttempt.objects
            .filter(user=request.user)
            .select_related(
                "exam", "exam__course", "session_video"
            )
            .order_by("-started_at")
        )
        return Response(
            {
                "success": True,
                "data": ExamAttemptSerializer(qs, many=True).data,
            }
        )


# ============================================================
# GET /api/attempts/<attempt_id>/
# ============================================================
class AttemptDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.select_related(
                "exam", "exam__course", "user", "session_video"
            ).get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response(
                {"success": False, "message": "Attempt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only the owner (or admin) can read
        if attempt.user_id != request.user.id and request.user.role not in (
            "admin",
            "super-admin",
        ):
            return Response(
                {"success": False, "message": "Not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "success": True,
                "data": ExamAttemptDetailSerializer(attempt).data,
            }
        )


# ============================================================
# GET /api/attempts/admin/
# ============================================================
class AdminAttemptsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            ExamAttempt.objects
            .select_related(
                "exam", "exam__course", "user", "session_video"
            )
            .order_by("-started_at")
        )
        return Response(
            {
                "success": True,
                "data": ExamAttemptSerializer(qs, many=True).data,
            }
        )


# ============================================================
# POST /api/attempts/<attempt_id>/mark-practical/
# Body: { practicalScore, practicalMax }
# ============================================================
class MarkPracticalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response(
                {"success": False, "message": "Attempt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            score = float(request.data.get("practicalScore"))
            maxpts = float(request.data.get("practicalMax"))
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "practicalScore and practicalMax required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        attempt.practical_score = score
        attempt.practical_max = maxpts
        attempt.practical_percent = round((score / maxpts) * 100, 2)

        # Weighted final = theory_percent * theory_weight%
        #                + practical_percent * practical_weight%
        tw = float(attempt.exam.theory_weight or 50)
        pw = float(attempt.exam.practical_weight or 50)
        theory_contrib = (float(attempt.theory_percent or 0) * tw) / 100
        practical_contrib = (attempt.practical_percent * pw) / 100

        final_pct = theory_contrib + practical_contrib
        attempt.final_percent = round(final_pct, 2)
        attempt.passed = final_pct >= float(
            attempt.exam.pass_threshold_pct or 50
        )

        # Grade
        if final_pct >= 80:
            grade = "A"
        elif final_pct >= 70:
            grade = "B+"
        elif final_pct >= 60:
            grade = "B"
        elif final_pct >= 50:
            grade = "C"
        elif final_pct >= 40:
            grade = "D"
        else:
            grade = "F"
        attempt.final_grade = grade

        attempt.marked_by = request.user
        attempt.marked_at = timezone.now()
        attempt.status = "marked"
        attempt.save(
            update_fields=[
                "practical_score",
                "practical_max",
                "practical_percent",
                "final_percent",
                "passed",
                "final_grade",
                "marked_by",
                "marked_at",
                "status",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,
                "message": "Practical marks saved.",
                "data": ExamAttemptSerializer(attempt).data,
            }
        )


# ============================================================
# POST /api/attempts/<attempt_id>/publish/
# ============================================================
class PublishAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response(
                {"success": False, "message": "Attempt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        attempt.status = "published"
        attempt.published_at = timezone.now()
        attempt.save(
            update_fields=["status", "published_at", "updated_at"]
        )

        return Response(
            {
                "success": True,
                "message": "Result published.",
                "data": ExamAttemptSerializer(attempt).data,
            }
        )



# ============================================================
# GET /api/attempts/<attempt_id>/review/
# Full detail for the admin review modal.
# ============================================================
class AdminAttemptReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        try:
            attempt = (
                ExamAttempt.objects
                .select_related(
                    "exam", "exam__course", "user", "session_video"
                )
                .get(id=attempt_id)
            )
        except ExamAttempt.DoesNotExist:
            return Response(
                {"success": False, "message": "Attempt not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "data": AdminAttemptReviewSerializer(attempt).data,
            }
        )