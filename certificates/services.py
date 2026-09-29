# certificates/services.py

"""
Certificate issuing service.

Source of truth: ``CourseEnrollment``.

A certificate exists for every course a candidate is enrolled in.
There is no exam-pass condition, no score threshold, and no
dependency on the enrollment view — this module reads enrollments
and writes certificates. Nothing else needs to cooperate.

Idempotent throughout: running it any number of times produces the
same set of certificate rows.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from enrollments.models import CourseEnrollment

from .models import Certificate
from .utils import (
    build_verification_url,
    generate_certificate_number,
    render_certificate_base64,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENSURE ONE CERTIFICATE FOR (user, course)
# ============================================================
def ensure_certificate(user, course) -> Certificate:
    """
    Return the certificate for (user, course), creating it if needed.
    Assumes the user is enrolled in the course — the caller is
    responsible for that check.
    """
    existing = (
        Certificate.objects
        .filter(user=user, course=course)
        .first()
    )
    if existing:
        return ensure_images(existing)

    number = generate_certificate_number()
    cert = Certificate.objects.create(
        certificate_number=number,
        user=user,
        course=course,
        grade="",
        final_percentage=None,
        # Placeholder; set to the UUID-based URL after save so the
        # QR code points at /certificates/verify/<uuid>.
        verification_url="",
    )
    cert.verification_url = build_verification_url(str(cert.id))
    cert.save(update_fields=["verification_url"])
    return ensure_images(cert)


# ============================================================
# ENSURE ONE CERTIFICATE PER ENROLLMENT FOR A USER
# ============================================================
def sync_certificates_for_user(user) -> list[Certificate]:
    """
    Fetch the user's enrollments and make sure a certificate exists
    for each. Returns the certificates, newest enrollment first.

    Called from the certificate views on every list/get request.
    Cheap when certificates already exist — no rendering happens.
    """
    enrollments = (
        CourseEnrollment.objects
        .filter(user=user)
        .select_related("course")
        .order_by("-enrolled_at")
    )

    certs: list[Certificate] = []
    for enrollment in enrollments:
        try:
            cert = ensure_certificate(user, enrollment.course)
            certs.append(cert)
        except Exception:
            logger.exception(
                "Failed to issue certificate for user=%s course=%s",
                user.id,
                enrollment.course_id,
            )
    return certs


# ============================================================
# RENDER PNGs (base64) — idempotent
# ============================================================
def ensure_images(cert: Certificate) -> Certificate:
    """
    Render both PNGs (clean + watermarked) and store them as base64
    on the Certificate row. No-op if they already exist.
    """
    if cert.image_data_url and cert.image_watermarked_data_url:
        return cert

    common = dict(
        certificate_number=cert.certificate_number,
        candidate_name=cert.user.full_name or cert.user.username,
        course_title=cert.course.title,
        grade=cert.grade,
        final_percentage=None,
        issue_date=cert.issued_at or timezone.now(),
        verification_url=cert.verification_url
        or build_verification_url(str(cert.id)),
    )

    try:
        cert.image_data_url = render_certificate_base64(
            **common, watermarked=False
        )
    except Exception:
        logger.exception("Clean certificate render failed")

    try:
        cert.image_watermarked_data_url = render_certificate_base64(
            **common, watermarked=True
        )
    except Exception:
        logger.exception("Watermarked certificate render failed")

    cert.save(
        update_fields=[
            "image_data_url",
            "image_watermarked_data_url",
            "updated_at",
        ]
    )
    return cert