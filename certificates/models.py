# certificates/models.py

from django.db import models
from django.conf import settings

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
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="certificates",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.RESTRICT,
        related_name="certificates",
    )

    # Grade
    grade = models.CharField(max_length=3, blank=True, null=True)
    final_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Verification
    verification_url = models.URLField(blank=True, null=True)
    qr_code_url = models.URLField(blank=True, null=True)

    # Rendered PNGs, stored as base64 data URLs.
    # `image_data_url`             → clean PNG.
    # `image_watermarked_data_url` → watermarked PNG.
    # Both are of the form ``data:image/png;base64,....``.
    image_data_url = models.TextField(blank=True, null=True)
    image_watermarked_data_url = models.TextField(blank=True, null=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=CertificateStatus.choices,
        default=CertificateStatus.ISSUED,
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True, null=True)

    # Admin control: hide / publish a certificate.
    # When False, the public verify endpoint returns valid=False and the
    # owner can no longer download the certificate.
    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "certificates"
        unique_together = [("user", "course")]
        indexes = [
            models.Index(fields=["user"], name="idx_certs_user"),
            models.Index(fields=["course"], name="idx_certs_course"),
            models.Index(
                fields=["certificate_number"], name="idx_certs_number"
            ),
            models.Index(fields=["status"], name="idx_certs_status"),
            models.Index(
                fields=["is_published"], name="idx_certs_published"
            ),
        ]

    def __str__(self):
        return f"{self.certificate_number} — {self.user.username}"


class CertificatePreview(TimeStampedModel):
    """
    Watermarked preview PNG for a candidate who scored below the
    pass mark. Stored as base64 so it can be served without any
    filesystem dependency.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificate_previews",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="certificate_previews",
    )
    image_data_url = models.TextField()
    final_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    class Meta:
        db_table = "certificate_previews"
        unique_together = [("user", "course")]

    def __str__(self):
        return f"Preview — {self.user.username} / {self.course.title}"