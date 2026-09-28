from django.shortcuts import render

# Create your views here.
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course
from .serializers import CourseSerializer, CourseWriteSerializer


# ============================================================
# GET /api/courses/           — list (public read)
# POST /api/courses/          — create (admin side)
# ============================================================
class CourseListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = Course.objects.filter(deleted_at__isnull=True).order_by("-created_at")

        # Filters
        search = (request.query_params.get("search") or "").strip()
        category = (request.query_params.get("category") or "").strip()
        status_filter = (request.query_params.get("status") or "").strip()

        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(category__icontains=search)
                | Q(instructor_name__icontains=search)
            )
        if category and category != "all":
            qs = qs.filter(category=category)
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)

        data = CourseSerializer(qs, many=True).data
        return Response({"success": True, "data": data})

    def post(self, request):
        ser = CourseWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Invalid course data", "errors": ser.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        course = ser.save()
        return Response(
            {
                "success": True,
                "message": "Course created.",
                "data": CourseSerializer(course).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# GET / PATCH / PUT / DELETE /api/courses/<uuid>/
# ============================================================
class CourseDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def _get(self, course_id):
        try:
            return Course.objects.get(id=course_id, deleted_at__isnull=True), None
        except Course.DoesNotExist:
            return None, Response(
                {"success": False, "message": "Course not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def get(self, request, course_id):
        course, err = self._get(course_id)
        if err:
            return err
        return Response({"success": True, "data": CourseSerializer(course).data})

    def patch(self, request, course_id):
        course, err = self._get(course_id)
        if err:
            return err
        ser = CourseWriteSerializer(course, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Invalid course data", "errors": ser.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        course = ser.save()
        return Response(
            {
                "success": True,
                "message": "Course updated.",
                "data": CourseSerializer(course).data,
            }
        )

    def put(self, request, course_id):
        return self.patch(request, course_id)

    def delete(self, request, course_id):
        course, err = self._get(course_id)
        if err:
            return err
        course.soft_delete()
        return Response({"success": True, "message": "Course deleted."})


# ============================================================
# POST /api/courses/<uuid>/delete/  — POST alias for delete
# ============================================================
class CourseDeletePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, deleted_at__isnull=True)
        except Course.DoesNotExist:
            return Response(
                {"success": False, "message": "Course not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        course.soft_delete()
        return Response({"success": True, "message": "Course deleted."})