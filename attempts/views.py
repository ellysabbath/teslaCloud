# attempts/views.py

"""
Endpoints for exam attempts: start, submit, mark, publish, review.

Matching-question marking
-------------------------
Correct answers are stored on ``Question.correct_matches`` as
``{ "0": "1", "1": "0" }`` — Column A index → Column B index.

Student answers are stored on ``AttemptMatchingAnswer`` as
``a_index`` / ``b_index`` integers (no UUID, no FK to the question's
columns), so the record survives any edit the admin makes to the
exam's columns after the attempt was taken.

Marking compares the two as **unordered sets of (aIndex, bIndex)
tuples** — order never matters, and re-saving the exam after the
student submitted never changes the score.
"""

from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exams.models import Exam
from questions.models import (
    Question,
    QuestionBooleanAnswer,
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
# HELPERS
# ============================================================
def _grade_from_pct(pct: float) -> str:
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B+"
    if pct >= 60:
        return "B"
    if pct >= 50:
        return "C"
    if pct >= 40:
        return "D"
    return "F"


def _norm_pairs(d) -> set:
    """
    Convert ``{"0": "1", "1": "0"}`` or ``{0: 1, 1: 0}`` into an
    unordered set of ``(int, int)`` tuples. Entries that cannot be
    coerced to int are skipped.
    """
    out = set()
    if not d:
        return out
    for a_key, b_key in d.items():
        try:
            out.add((int(a_key), int(b_key)))
        except (TypeError, ValueError):
            continue
    return out


# ============================================================
# AUTO-MARK
# ============================================================
def _auto_mark(attempt: ExamAttempt) -> None:
    """
    Grade all theory questions on an attempt.

    Each question contributes ``section.points_per_question`` to the
    total. A question is correct when:

      * multiple-choice: the selected option is marked ``is_correct``
      * true-false:      the submitted boolean equals
                         ``question.boolean_answer.correct_value``
      * matching:        the set of ``(a_index, b_index)`` pairs on
                         ``AttemptMatchingAnswer`` equals the set
                         parsed from ``Question.correct_matches``
      * fill-blank:      the submitted text (case-insensitive,
                         stripped) matches one of the accepted
                         answers on ``question.fill_blank_answers``
    """
    total_points = 0.0
    earned_points = 0.0

    # Wipe any previous marking rows so re-running is safe.
    attempt.marking_results.all().delete()

    sections = attempt.exam.sections.all().prefetch_related("questions")

    for section in sections:
        pts_per_q = float(section.points_per_question or 0)

        for question in section.questions.all():
            total_points += pts_per_q
            is_correct = False

            # ------------------------------------------------------
            # MULTIPLE-CHOICE / TRUE-FALSE / FILL-BLANK
            #   These store their answer in AttemptAnswer.
            # ------------------------------------------------------
            if question.type in (
                "multiple-choice",
                "true-false",
                "fill-blank",
            ):
                answer = attempt.answers.filter(
                    question=question
                ).first()

                if answer:
                    if question.type == "multiple-choice":
                        if (
                            answer.selected_option
                            and answer.selected_option.is_correct
                        ):
                            is_correct = True

                    elif question.type == "true-false":
                        try:
                            correct = (
                                question.boolean_answer.correct_value
                            )
                            if answer.boolean_answer == correct:
                                is_correct = True
                        except QuestionBooleanAnswer.DoesNotExist:
                            pass

                    elif question.type == "fill-blank":
                        accepted = [
                            a.answer_text.strip().lower()
                            for a in question.fill_blank_answers.all()
                        ]
                        given_text = (
                            answer.text_answer or ""
                        ).strip().lower()
                        if given_text and given_text in accepted:
                            is_correct = True

            # ------------------------------------------------------
            # MATCHING
            #   Stored in AttemptMatchingAnswer, not in AttemptAnswer.
            #   This branch runs regardless of whether an AttemptAnswer
            #   row exists, because matching questions never create one.
            # ------------------------------------------------------
            elif question.type == "matching":
                expected = _norm_pairs(
                    question.correct_matches or {}
                )
                given = {
                    str(m.a_index): (
                        str(m.b_index)
                        if m.b_index is not None
                        else ""
                    )
                    for m in attempt.matching_answers.filter(
                        question=question
                    )
                }
                given_set = _norm_pairs(given)

                if expected and expected == given_set:
                    is_correct = True

            # ------------------------------------------------------
            # RECORD RESULT
            # ------------------------------------------------------
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
        (earned_points / total_points) * 100
        if total_points > 0
        else 0
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

            # Non-matching types go into AttemptAnswer.
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

            # Matching goes into AttemptMatchingAnswer as index pairs.
            elif question.type == "matching":
                matches = raw.get("matches") or {}
                for a_key, b_key in matches.items():
                    try:
                        a_idx = int(a_key)
                        b_idx = int(b_key)
                    except (TypeError, ValueError):
                        continue
                    AttemptMatchingAnswer.objects.create(
                        attempt=attempt,
                        question=question,
                        a_index=a_idx,
                        b_index=b_idx,
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
                file_size=len(video_b64) * 3 // 4,
            )
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
                "session_video",
                "updated_at",
            ]
        )

        # ---------- Auto-mark theory ----------
        _auto_mark(attempt)

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
            .select_related("exam", "exam__course", "session_video")
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
            .select_related("exam", "exam__course", "user", "session_video")
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

        if maxpts <= 0:
            return Response(
                {
                    "success": False,
                    "message": "practicalMax must be greater than 0",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if score < 0:
            return Response(
                {
                    "success": False,
                    "message": "practicalScore cannot be negative",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        attempt.practical_score = score
        attempt.practical_max = maxpts
        attempt.practical_percent = round((score / maxpts) * 100, 2)

        tw = float(attempt.exam.theory_weight or 50)
        pw = float(attempt.exam.practical_weight or 50)
        threshold = float(attempt.exam.pass_threshold_pct or 50)

        theory_contrib = (float(attempt.theory_percent or 0) * tw) / 100
        practical_contrib = (attempt.practical_percent * pw) / 100
        final_pct = theory_contrib + practical_contrib

        attempt.final_percent = round(final_pct, 2)
        attempt.passed = final_pct >= threshold
        attempt.final_grade = _grade_from_pct(final_pct)

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

        if attempt.final_percent is None:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Mark the practical component before publishing."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
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