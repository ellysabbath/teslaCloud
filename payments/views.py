from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course
from enrollments.models import CourseEnrollment

from .models import Payment
from .serializers import PaymentSerializer, PaymentSubmitSerializer


# ============================================================
# HELPER — confirm a payment & auto-enroll
# ============================================================
def _confirm_payment(payment: Payment) -> Payment:
    with transaction.atomic():
        payment.status = "paid"
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at", "updated_at"])

        CourseEnrollment.objects.get_or_create(
            user=payment.user,
            course=payment.course,
            defaults={"status": "active"},
        )
    return payment


# ============================================================
# GET /api/payments/mine/
# ============================================================
class MyPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Payment.objects
            .filter(user=request.user)
            .select_related("course")
            .order_by("-created_at")
        )
        return Response(
            {"success": True, "data": PaymentSerializer(qs, many=True).data}
        )


# ============================================================
# GET /api/payments/admin/
# ============================================================
class AdminPaymentsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Payment.objects
            .select_related("course", "user")
            .order_by("-created_at")
        )
        return Response(
            {"success": True, "data": PaymentSerializer(qs, many=True).data}
        )


# ============================================================
# POST /api/payments/submit/
# ============================================================
class SubmitPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PaymentSubmitSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {"success": False, "message": "Invalid payment data", "errors": ser.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            course = Course.objects.get(
                id=ser.validated_data["courseId"], deleted_at__isnull=True
            )
        except Course.DoesNotExist:
            return Response(
                {"success": False, "message": "Course not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        already = Payment.objects.filter(
            user=request.user, course=course, status="paid"
        ).exists()
        if already:
            return Response(
                {"success": False, "message": "You are already enrolled in this course"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = Payment.objects.create(
            user=request.user,
            course=course,
            amount=course.price,
            currency=course.currency,
            method=ser.validated_data["method"],
            reference=ser.validated_data["reference"].strip().upper(),
            phone_paid_from=ser.validated_data.get("phonePaidFrom") or None,
            status="pending",
        )

        return Response(
            {
                "success": True,
                "message": "Payment submitted. Awaiting admin confirmation.",
                "data": PaymentSerializer(payment).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# POST /api/payments/<uuid>/mark-paid/
# ============================================================
class AdminMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "message": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        _confirm_payment(payment)

        return Response(
            {
                "success": True,
                "message": (
                    f"Payment {payment.reference} confirmed and "
                    f"{payment.user.full_name} enrolled in {payment.course.title}."
                ),
                "data": PaymentSerializer(payment).data,
            }
        )


# ============================================================
# POST /api/payments/<uuid>/fail/
# ============================================================
class AdminMarkFailedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "message": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "failed"
        payment.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"Payment {payment.reference} marked as failed.",
                "data": PaymentSerializer(payment).data,
            }
        )


# ============================================================
# POST /api/payments/<uuid>/refund/
# ============================================================
class AdminRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "message": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "refunded"
        payment.save(update_fields=["status", "updated_at"])

        # Also drop the enrollment if it exists
        CourseEnrollment.objects.filter(
            user=payment.user, course=payment.course
        ).update(status="dropped")

        return Response(
            {
                "success": True,
                "message": f"Payment {payment.reference} refunded.",
                "data": PaymentSerializer(payment).data,
            }
        )


# ============================================================
# DELETE-like: POST /api/payments/<uuid>/delete/
# ============================================================
class AdminDeletePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"success": False, "message": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.delete()
        return Response({"success": True, "message": "Payment deleted."})