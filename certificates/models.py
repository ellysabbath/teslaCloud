from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models

from core.enums import CertificateStatus
from core.models import TimeStampedModel


class CertificateSequence(models.Model):
    """Atomic counter for TCI-YYYY-NNNN certificate numbers, per year."""
    year = models.CharField(max_length=4, primary_key=True)
    last_sequence = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "certificate_sequences"

    def __str__(self):
        return f"{self.year} → {self.last_sequence}"


class Certificate(TimeStampedModel):
    certificate_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="certificates"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.RESTRICT, related_name="certificates"
    )

    # Grade
    grade = models.CharField(max_length=3, blank=True, null=True)
    final_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Verification
    verification_url = models.URLField(blank=True, null=True)
    qr_code_url = models.URLField(blank=True, null=True)

    # Status
    status = models.CharField(
        max_length=20, choices=CertificateStatus.choices, default=CertificateStatus.ISSUED
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "certificates"
        unique_together = [("user", "course")]
        indexes = [
            models.Index(fields=["user"], name="idx_certs_user"),
            models.Index(fields=["course"], name="idx_certs_course"),
            models.Index(fields=["certificate_number"], name="idx_certs_number"),
            models.Index(fields=["status"], name="idx_certs_status"),
        ]

    def __str__(self):
        return f"{self.certificate_number} — {self.user.username}"