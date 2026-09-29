# attempts/models.py

import uuid

from django.conf import settings
from django.db import models

from core.enums import AnswerStatus
from core.models import TimeStampedModel


# ============================================================
# ATTEMPT
# ============================================================
class ExamAttempt(TimeStampedModel):
    exam = models.ForeignKey(
        "exams.Exam", on_delete=models.RESTRICT, related_name="attempts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    auto_submitted = models.BooleanField(default=False)
    auto_submit_reason = models.CharField(
        max_length=100, blank=True, null=True
    )

    session_video = models.ForeignKey(
        "users.UserVideo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attempts",
    )

    # Theory (auto-marked)
    theory_earned = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    theory_total = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    theory_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Practical (admin-marked)
    practical_score = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    practical_max = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    practical_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Final
    final_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    final_grade = models.CharField(max_length=3, blank=True, null=True)
    passed = models.BooleanField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=AnswerStatus.choices,
        default=AnswerStatus.PENDING,
    )

    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attempts_marked",
    )
    marked_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "exam_attempts"
        unique_together = [("exam", "user")]
        indexes = [
            models.Index(fields=["user"], name="idx_attempts_user"),
            models.Index(fields=["exam"], name="idx_attempts_exam"),
            models.Index(fields=["status"], name="idx_attempts_status"),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.exam.title}"


# ============================================================
# ATTEMPT ANSWER — non-matching types
# ============================================================
class AttemptAnswer(models.Model):
    """A candidate's answer to a single non-matching question."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        "questions.Question", on_delete=models.RESTRICT
    )

    selected_option = models.ForeignKey(
        "questions.QuestionOption",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    boolean_answer = models.BooleanField(null=True, blank=True)
    text_answer = models.TextField(blank=True, null=True)

    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attempt_answers"
        unique_together = [("attempt", "question")]
        indexes = [
            models.Index(fields=["attempt"], name="idx_answers_attempt"),
            models.Index(fields=["question"], name="idx_answers_question"),
        ]


# ============================================================
# ATTEMPT MATCHING ANSWER — index-based, no UUIDs
# ============================================================
class AttemptMatchingAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="matching_answers"
    )
    question = models.ForeignKey(
        "questions.Question", on_delete=models.CASCADE
    )
    a_index = models.IntegerField()
    b_index = models.IntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attempt_matching_answers"
        unique_together = [("attempt", "question", "a_index")]
        indexes = [
            models.Index(fields=["attempt"], name="idx_attempt_match_attempt"),
        ]

# ============================================================
# ATTEMPT MARKING RESULT — unchanged
# ============================================================
class AttemptMarkingResult(models.Model):
    """Per-question auto-marking outcome."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="marking_results"
    )
    question = models.ForeignKey(
        "questions.Question", on_delete=models.CASCADE
    )
    correct = models.BooleanField()
    awarded = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_points = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attempt_marking_results"
        unique_together = [("attempt", "question")]
        indexes = [
            models.Index(fields=["attempt"], name="idx_marking_attempt"),
        ]