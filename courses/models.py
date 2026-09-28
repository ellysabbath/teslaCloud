from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify

from core.enums import CourseStatus
from core.models import TimeStampedModel, SoftDeleteModel


class Course(TimeStampedModel, SoftDeleteModel):
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    full_description = models.TextField(blank=True, null=True)
    why_learn = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)

    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="TZS")

    duration = models.CharField(max_length=50, blank=True, null=True)
    practicals_count = models.IntegerField(default=0)
    theory_days = models.CharField(max_length=100, blank=True, null=True)
    practical_days = models.CharField(max_length=100, blank=True, null=True)
    theory_exam = models.CharField(max_length=100, blank=True, null=True)
    practical_exam = models.CharField(max_length=100, blank=True, null=True)

    image_url = models.URLField(blank=True, null=True)

    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="courses_taught",
    )
    instructor_name = models.CharField(max_length=150, blank=True, null=True)

    status = models.CharField(
        max_length=20, choices=CourseStatus.choices, default=CourseStatus.PUBLISHED
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="courses_created",
    )

    class Meta:
        db_table = "courses"
        indexes = [
            models.Index(fields=["status"], name="idx_courses_status"),
            models.Index(fields=["category"], name="idx_courses_category"),
            models.Index(fields=["instructor"], name="idx_courses_instructor"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:200]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CourseLearningOutcome(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="learning_outcomes"
    )
    outcome = models.TextField()
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "course_learning_outcomes"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["course", "sort_order"], name="idx_outcomes_course"),
        ]

    def __str__(self):
        return f"{self.course.title} — #{self.sort_order}"