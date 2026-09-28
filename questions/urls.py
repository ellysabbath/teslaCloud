from django.urls import path

from .views import SectionQuestionsBulkView, SectionQuestionsListView

app_name = "questions"

urlpatterns = [
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