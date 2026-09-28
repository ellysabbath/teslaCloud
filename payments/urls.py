from django.urls import path

from .views import (
    AdminDeletePaymentView,
    AdminMarkFailedView,
    AdminMarkPaidView,
    AdminPaymentsListView,
    AdminRefundView,
    MyPaymentsView,
    SubmitPaymentView,
)

app_name = "payments"

urlpatterns = [
    path("mine/", MyPaymentsView.as_view(), name="my-payments"),
    path("admin/", AdminPaymentsListView.as_view(), name="admin-list"),
    path("submit/", SubmitPaymentView.as_view(), name="submit"),
    path("<uuid:payment_id>/mark-paid/", AdminMarkPaidView.as_view(), name="mark-paid"),
    path("<uuid:payment_id>/fail/", AdminMarkFailedView.as_view(), name="mark-failed"),
    path("<uuid:payment_id>/refund/", AdminRefundView.as_view(), name="refund"),
    path("<uuid:payment_id>/delete/", AdminDeletePaymentView.as_view(), name="delete"),
]