from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=100)  # user.register | exam.publish | ...
    entity_type = models.CharField(max_length=50, blank=True, null=True)
    entity_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"], name="idx_audit_user"),
            models.Index(fields=["action"], name="idx_audit_action"),
            models.Index(fields=["entity_type", "entity_id"], name="idx_audit_entity"),
            models.Index(fields=["-created_at"], name="idx_audit_created"),
        ]

    def __str__(self):
        return f"{self.action} — {self.created_at}"