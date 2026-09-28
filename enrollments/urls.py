from django.urls import path

from .views import (
    AdminUserEnrollmentsView,
    EnrollInCourseView,
    MyEnrollmentsView,
    UnenrollView,
)

app_name = "enrollments"

urlpatterns = [
    path("mine/", MyEnrollmentsView.as_view(), name="my-enrollments"),
    path(
        "admin/user/<uuid:user_id>/",
        AdminUserEnrollmentsView.as_view(),
        name="admin-user-enrollments",
    ),
    path("enroll/<uuid:course_id>/", EnrollInCourseView.as_view(), name="enroll"),
    path("unenroll/<uuid:course_id>/", UnenrollView.as_view(), name="unenroll"),
]