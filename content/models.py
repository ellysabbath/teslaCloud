from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class NewsItem(TimeStampedModel):
    title = models.CharField(max_length=255)
    body = models.TextField()
    image_url = models.URLField(blank=True, null=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="news_created",
    )

    class Meta:
        db_table = "news_items"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["-published_at"], name="idx_news_published"),
        ]

    def __str__(self):
        return self.title


class Testimonial(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="testimonials",
    )
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True, null=True)
    message = models.TextField()
    image_url = models.URLField(blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="testimonials_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "testimonials"
        indexes = [
            models.Index(fields=["is_approved"], name="idx_testimonials_approved"),
        ]

    def __str__(self):
        return f"{self.name} — {self.role or ''}"


class TeamMember(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="team_profile",
    )
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100)
    image_url = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "team_members"
        ordering = ["sort_order"]

    def __str__(self):
        return f"{self.name} — {self.role}"