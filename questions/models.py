# questions/models.py

import uuid

from django.db import models

from core.enums import QuestionType
from exams.models import ExamSection


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        ExamSection, on_delete=models.CASCADE, related_name="questions"
    )
    type = models.CharField(max_length=30, choices=QuestionType.choices)
    text = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    # Correct matching scheme stored as ``{ "aIndex": "bIndex" }``.
    # Indices refer to the current position of the row in
    # ``MatchingColumnA`` / ``MatchingColumnB`` (ordered by sort_order).
    # Only used when ``type == "matching"``; empty dict otherwise.
    # Stored here — rather than in the legacy ``MatchingScheme`` table —
    # so auto-marking never depends on column UUIDs, which are regenerated
    # every time the admin re-saves the exam.
    correct_matches = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "questions"
        ordering = ["sort_order"]
        indexes = [
            models.Index(
                fields=["section", "sort_order"],
                name="idx_questions_section",
            ),
        ]

    def __str__(self):
        preview = (self.text or "")[:40]
        return f"Q ({self.type}) — {preview}"


class QuestionOption(models.Model):
    """Multiple-choice options. Exactly one row per question must have is_correct=True."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "question_options"
        ordering = ["sort_order"]
        indexes = [
            models.Index(
                fields=["question", "sort_order"],
                name="idx_options_question",
            ),
        ]

    def __str__(self):
        return f"{'✓' if self.is_correct else ' '} {self.option_text[:40]}"


class QuestionBooleanAnswer(models.Model):
    """True/False correct value."""

    question = models.OneToOneField(
        Question,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="boolean_answer",
    )
    correct_value = models.BooleanField()

    class Meta:
        db_table = "question_boolean_answers"

    def __str__(self):
        return f"Q {self.question_id} → {self.correct_value}"


class MatchingColumnA(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="matching_column_a"
    )
    item_text = models.TextField()
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "matching_column_a"
        ordering = ["sort_order"]
        indexes = [
            models.Index(
                fields=["question", "sort_order"],
                name="idx_match_a_q",
            ),
        ]


class MatchingColumnB(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="matching_column_b"
    )
    item_text = models.TextField()
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "matching_column_b"
        ordering = ["sort_order"]
        indexes = [
            models.Index(
                fields=["question", "sort_order"],
                name="idx_match_b_q",
            ),
        ]


class MatchingScheme(models.Model):
    """
    Legacy marking scheme: Column A item → Column B item.

    Kept for backward compatibility with exams saved before
    ``Question.correct_matches`` existed. New saves write to the
    JSONField instead; this table is no longer created by the admin
    builder. Safe to drop after a data migration if you no longer
    need it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="matching_scheme"
    )
    column_a = models.ForeignKey(
        MatchingColumnA, on_delete=models.CASCADE
    )
    column_b = models.ForeignKey(
        MatchingColumnB, on_delete=models.CASCADE
    )

    class Meta:
        db_table = "matching_scheme"
        unique_together = [
            ("question", "column_a"),
            ("question", "column_b"),
        ]


class FillBlankAnswer(models.Model):
    """Fill-in-the-blank correct answers. One must be primary."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="fill_blank_answers"
    )
    answer_text = models.TextField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fill_blank_answers"
        indexes = [
            models.Index(fields=["question"], name="idx_fill_blank_q"),
        ]