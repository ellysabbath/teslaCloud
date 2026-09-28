from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model

User = get_user_model()

from courses.models import Course

from .models import CourseEnrollment
from .serializers import EnrollmentSerializer


class MyEnrollmentsView(APIView):
    """
    GET /api/enrollments/mine/
    Returns the logged-in user's enrollments, newest first.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            CourseEnrollment.objects
            .filter(user=request.user)
            .select_related("course")
            .order_by("-enrolled_at")
        )
        return Response(
            {"success": True, "data": EnrollmentSerializer(qs, many=True).data}
        )


class EnrollInCourseView(APIView):
    """
    POST /api/enrollments/enroll/<course_id>/
    Direct enrollment (used by admins / tests).
    In the normal user flow, enrollment is created automatically
    when a payment is confirmed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, deleted_at__isnull=True)
        except Course.DoesNotExist:
            return Response(
                {"success": False, "message": "Course not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        enrollment, created = CourseEnrollment.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={"status": "active"},
        )

        return Response(
            {
                "success": True,
                "message": "Enrolled successfully" if created else "Already enrolled",
                "data": EnrollmentSerializer(enrollment).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UnenrollView(APIView):
    """
    POST /api/enrollments/unenroll/<course_id>/
    Marks the user's enrollment as dropped.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        try:
            enrollment = CourseEnrollment.objects.get(
                user=request.user, course_id=course_id
            )
        except CourseEnrollment.DoesNotExist:
            return Response(
                {"success": False, "message": "You are not enrolled in that course"},
                status=status.HTTP_404_NOT_FOUND,
            )

        enrollment.status = "dropped"
        enrollment.save(update_fields=["status", "updated_at"])

        return Response({"success": True, "message": "Left the course."})




class AdminUserEnrollmentsView(APIView):
    """
    GET /api/enrollments/admin/user/<user_id>/
    Returns the given user's enrollments — admin use only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = (
            CourseEnrollment.objects
            .filter(user=user)
            .select_related("course")
            .order_by("-enrolled_at")
        )

        return Response(
            {
                "success": True,
                "data": EnrollmentSerializer(qs, many=True).data,
            }
        )