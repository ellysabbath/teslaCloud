from django.urls import path

from .views import (
    AdminAttemptsListView,
    AdminAttemptReviewView,            # ← new
    AttemptDetailView,
    MarkPracticalView,
    MyAttemptsView,
    PublishAttemptView,
    StartAttemptView,
    SubmitAttemptView,
)

app_name = "attempts"

urlpatterns = [
    # Student
    path("mine/", MyAttemptsView.as_view(), name="mine"),
    path("start/<uuid:exam_id>/", StartAttemptView.as_view(), name="start"),
    path("<uuid:attempt_id>/", AttemptDetailView.as_view(), name="detail"),
    path("<uuid:attempt_id>/submit/", SubmitAttemptView.as_view(), name="submit"),

    # Admin
    path("admin/", AdminAttemptsListView.as_view(), name="admin-list"),
    path(
        "<uuid:attempt_id>/review/",
        AdminAttemptReviewView.as_view(),
        name="admin-review",
    ),
    path(
        "<uuid:attempt_id>/mark-practical/",
        MarkPracticalView.as_view(),
        name="mark-practical",
    ),
    path(
        "<uuid:attempt_id>/publish/",
        PublishAttemptView.as_view(),
        name="publish",
    ),
]