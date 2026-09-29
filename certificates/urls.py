# certificates/urls.py

from django.urls import path

from .views import (
    MyCertificatesView,
    CertificateDetailView,
    CertificatePreviewView,
    CertificateVerifyView,
    AdminCertificateListView,
    AdminCertificatePublishView,
)

urlpatterns = [
    # Owner
    path("mine/", MyCertificatesView.as_view(), name="certificates-mine"),

    # Admin list (must come BEFORE the <uuid> catch-all)
    path(
        "admin/",
        AdminCertificateListView.as_view(),
        name="certificates-admin-list",
    ),
    path(
        "admin/<uuid:certificate_id>/publish/",
        AdminCertificatePublishView.as_view(),
        name="certificates-admin-publish",
    ),

    # Public verification
    path(
        "verify/<uuid:certificate_id>/",
        CertificateVerifyView.as_view(),
        name="certificates-verify",
    ),

    # Preview for a course
    path(
        "preview/<int:course_id>/",
        CertificatePreviewView.as_view(),
        name="certificates-preview",
    ),

    # Single certificate (must come LAST — it is the catch-all)
    path(
        "<uuid:certificate_id>/",
        CertificateDetailView.as_view(),
        name="certificates-detail",
    ),
]