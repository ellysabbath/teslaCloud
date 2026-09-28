from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models

from core.enums import PaymentMethod, PaymentStatus
from core.models import TimeStampedModel


class PaymentMethodInfo(TimeStampedModel):
    """Reference table for payment method metadata (Lipa Namba, instructions, etc.)."""
    name = models.CharField(max_length=30, choices=PaymentMethod.choices, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    lipa_namba = models.CharField(max_length=50, blank=True, null=True)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "payment_methods"

    def __str__(self):
        return self.display_name


class Payment(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="payments"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.RESTRICT, related_name="payments"
    )
    enrollment = models.ForeignKey(
        "enrollments.CourseEnrollment",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payments",
    )

    # Amount
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")

    # Method
    method = models.CharField(max_length=30, choices=PaymentMethod.choices)
    method_info = models.ForeignKey(
        PaymentMethodInfo, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Customer-submitted data
    phone_paid_from = models.CharField(max_length=20, blank=True, null=True)
    reference = models.CharField(max_length=100)

    # Status
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )

    # Audit
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payments_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "payments"
        unique_together = [("method", "reference")]
        indexes = [
            models.Index(fields=["user"], name="idx_payments_user"),
            models.Index(fields=["course"], name="idx_payments_course"),
            models.Index(fields=["status"], name="idx_payments_status"),
            models.Index(fields=["reference"], name="idx_payments_ref"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.amount} {self.currency} ({self.status})"