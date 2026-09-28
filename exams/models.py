from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models

from core.enums import ExamStatus, SectionKind
from core.models import TimeStampedModel, SoftDeleteModel


class Exam(TimeStampedModel, SoftDeleteModel):
    title = models.CharField(max_length=255)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.RESTRICT, related_name="exams"
    )
    year = models.CharField(max_length=4)

    duration_minutes = models.IntegerField(default=60)
    theory_weight = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    practical_weight = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    pass_threshold_pct = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)

    status = models.CharField(
        max_length=20, choices=ExamStatus.choices, default=ExamStatus.DRAFT
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="exams_created",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "exams"
        indexes = [
            models.Index(fields=["course"], name="idx_exams_course"),
            models.Index(fields=["status"], name="idx_exams_status"),
            models.Index(fields=["year"], name="idx_exams_year"),
        ]

    def __str__(self):
        return f"{self.title} ({self.year})"


class ExamInstruction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="instructions")
    instruction = models.TextField()
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exam_instructions"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["exam", "sort_order"], name="idx_exam_instr_exam"),
        ]

    def __str__(self):
        return f"{self.exam.title} — #{self.sort_order}"


class ExamSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=50, choices=SectionKind.choices)
    instructions = models.TextField(blank=True, null=True)
    points_per_question = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exam_sections"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["exam", "sort_order"], name="idx_sections_exam"),
        ]

    def __str__(self):
        return f"{self.exam.title} — {self.title}"