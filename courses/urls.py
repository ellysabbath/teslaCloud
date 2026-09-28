from django.urls import path

from .views import (
    CourseDeletePostView,
    CourseDetailView,
    CourseListCreateView,
)

app_name = "courses"

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="list-create"),
    path("<uuid:course_id>/", CourseDetailView.as_view(), name="detail"),
    path("<uuid:course_id>/delete/", CourseDeletePostView.as_view(), name="delete-post"),
]