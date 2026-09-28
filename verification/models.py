from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models


class VerificationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_tokens",
    )
    token = models.CharField(max_length=255, unique=True)
    purpose = models.CharField(max_length=50)  # email_verify | password_reset | login_2fa
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "verification_tokens"
        indexes = [
            models.Index(fields=["user"], name="idx_verif_tokens_user"),
            models.Index(fields=["token"], name="idx_verif_tokens_token"),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.purpose}"