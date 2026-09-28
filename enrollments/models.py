from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models

from core.enums import EnrollmentStatus
from core.models import TimeStampedModel


class CourseEnrollment(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
    )

    class Meta:
        db_table = "course_enrollments"
        unique_together = [("user", "course")]
        indexes = [
            models.Index(fields=["user"], name="idx_enroll_user"),
            models.Index(fields=["course"], name="idx_enroll_course"),
            models.Index(fields=["status"], name="idx_enroll_status"),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.course.title}"