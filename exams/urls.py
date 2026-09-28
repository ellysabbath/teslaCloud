from django.urls import path

from questions.views import (
    SectionQuestionsBulkView,
    SectionQuestionsListView,
)

from .views import (
    ExamCloseView,
    ExamDeletePostView,
    ExamDetailView,
    ExamInstructionsBulkView,
    ExamListCreateView,
    ExamPublishView,
    ExamSectionsBulkView,
)

app_name = "exams"

urlpatterns = [
    # Exam CRUD
    path("", ExamListCreateView.as_view(), name="list-create"),
    path("<uuid:exam_id>/", ExamDetailView.as_view(), name="detail"),
    path("<uuid:exam_id>/delete/", ExamDeletePostView.as_view(), name="delete-post"),
    path("<uuid:exam_id>/publish/", ExamPublishView.as_view(), name="publish"),
    path("<uuid:exam_id>/close/", ExamCloseView.as_view(), name="close"),
    path(
        "<uuid:exam_id>/instructions/",
        ExamInstructionsBulkView.as_view(),
        name="instructions",
    ),
    path(
        "<uuid:exam_id>/sections/",
        ExamSectionsBulkView.as_view(),
        name="sections",
    ),

    # Questions inside a section
    path(
        "sections/<uuid:section_id>/questions/",
        SectionQuestionsListView.as_view(),
        name="section-questions-list",
    ),
    path(
        "sections/<uuid:section_id>/questions/save/",
        SectionQuestionsBulkView.as_view(),
        name="section-questions-save",
    ),
]