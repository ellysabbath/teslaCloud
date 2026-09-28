"""
exams/views.py

Exam management endpoints.

Design notes
------------
* Every write endpoint that touches more than one row is wrapped in
  ``@transaction.atomic`` so a partial save can never corrupt an exam.
* Sections and questions are **upserted** by their UUID. The old
  "delete-all then recreate" strategy is gone — it triggered Django's
  ``RestrictedError`` the moment any candidate had answered a question
  (``AttemptAnswer.question`` uses ``on_delete=RESTRICT``).
* When the client wants to remove a section or question that already
  has answers, the endpoint returns ``409 Conflict`` with a human
  message instead of blowing up with a 500.
* Client-generated ids (``"local-..."``) are treated as "create new".
  Real UUIDs that match existing rows mean "update in place".
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Exam,
    ExamInstruction,
    
    ExamSection,
)
from questions.models import Question
from .serializers import (
    ExamInstructionSerializer,
    
    ExamSectionWriteSerializer,
    ExamSerializer,
    ExamWriteSerializer,
)
from questions.serializers import QuestionWriteSerializer


# ============================================================
# Helpers
# ============================================================

def _is_local_id(value) -> bool:
    """
    Client-side placeholder ids look like ``local-<uuid>``.
    Anything falsy, non-string, or starting with ``local-`` is
    considered a "create new" signal.
    """
    if not value:
        return True
    if not isinstance(value, str):
        return True
    return value.startswith("local-")


def _answers_for_section(section):
    from attempts.models import AttemptAnswer  # local import: optional app
    return AttemptAnswer.objects.filter(question__section=section)


def _answers_for_question(question):
    from attempts.models import AttemptAnswer  # local import: optional app
    return AttemptAnswer.objects.filter(question=question)


def _get_exam_or_404(exam_id):
    """Return (exam, None) or (None, Response 404)."""
    try:
        exam = (
            Exam.objects
            .select_related("course")
            .get(id=exam_id, deleted_at__isnull=True)
        )
        return exam, None
    except Exam.DoesNotExist:
        return None, Response(
            {"success": False, "message": "Exam not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


def _get_section_or_404(section_id):
    """Return (section, None) or (None, Response 404)."""
    try:
        section = (
            ExamSection.objects
            .select_related("exam")
            .get(id=section_id, exam__deleted_at__isnull=True)
        )
        return section, None
    except ExamSection.DoesNotExist:
        return None, Response(
            {"success": False, "message": "Section not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


# ============================================================
# LIST + CREATE
# GET  /api/exams/     — list (public)
# POST /api/exams/     — create (auth)
# ============================================================

class ExamListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = (
            Exam.objects
            .filter(deleted_at__isnull=True)
            .select_related("course")
            .prefetch_related("instructions", "sections")
            .order_by("-created_at")
        )

        status_filter = (request.query_params.get("status") or "").strip()
        course_id = (request.query_params.get("courseId") or "").strip()
        search = (request.query_params.get("search") or "").strip()

        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(course__title__icontains=search)
            )

        return Response(
            {"success": True, "data": ExamSerializer(qs, many=True).data}
        )

    @transaction.atomic
    def post(self, request):
        ser = ExamWriteSerializer(
            data=request.data, context={"request": request}
        )
        if not ser.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Invalid exam data",
                    "errors": ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam = ser.save()
        return Response(
            {
                "success": True,
                "message": "Exam created.",
                "data": ExamSerializer(exam).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# DETAIL — GET / PATCH / PUT / DELETE
# /api/exams/<uuid>/
# ============================================================

class ExamDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err
        return Response({"success": True, "data": ExamSerializer(exam).data})

    @transaction.atomic
    def patch(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err

        ser = ExamWriteSerializer(
            exam,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not ser.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Invalid exam data",
                    "errors": ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        exam = ser.save()
        return Response(
            {
                "success": True,
                "message": "Exam updated.",
                "data": ExamSerializer(exam).data,
            }
        )

    def put(self, request, exam_id):
        return self.patch(request, exam_id)

    @transaction.atomic
    def delete(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err
        exam.soft_delete()
        return Response({"success": True, "message": "Exam deleted."})


# ============================================================
# ACTION ALIASES
# POST /api/exams/<uuid>/delete/
# POST /api/exams/<uuid>/publish/
# POST /api/exams/<uuid>/close/
# ============================================================

class ExamDeletePostView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err
        exam.soft_delete()
        return Response({"success": True, "message": "Exam deleted."})


class ExamPublishView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err

        exam.status = "published"
        exam.published_at = timezone.now()
        exam.save(update_fields=["status", "published_at", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"{exam.title} published.",
                "data": ExamSerializer(exam).data,
            }
        )


class ExamCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err

        exam.status = "closed"
        exam.closed_at = timezone.now()
        exam.save(update_fields=["status", "closed_at", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"{exam.title} closed.",
                "data": ExamSerializer(exam).data,
            }
        )


# ============================================================
# INSTRUCTIONS
# POST /api/exams/<exam_id>/instructions/
#
# Bulk replace. Instructions are never referenced by attempts,
# so a wipe-and-rewrite is safe here.
# ============================================================

class ExamInstructionsBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err

        items = request.data.get("instructions") or []
        if not isinstance(items, list):
            return Response(
                {"success": False, "message": "instructions must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exam.instructions.all().delete()

        created = []
        for idx, raw in enumerate(items):
            text = (raw or "").strip() if isinstance(raw, str) else ""
            if not text:
                continue
            created.append(
                ExamInstruction.objects.create(
                    exam=exam, instruction=text, sort_order=idx
                )
            )

        return Response(
            {
                "success": True,
                "message": "Instructions updated.",
                "data": ExamInstructionSerializer(created, many=True).data,
            }
        )


# ============================================================
# SECTIONS — UPSERT
# POST /api/exams/<exam_id>/sections/
#
# Body:
#   {
#     "sections": [
#       {
#         "id": <uuid|null>,
#         "title": "...",
#         "kind": "Multiple Choice Questions" | ...,
#         "instructions": "...",
#         "points_per_question": 1
#       },
#       ...
#     ]
#   }
#
# Rules
# -----
# * id matches an existing section  → update in place
# * id absent / "local-..."         → create new
# * existing section missing from payload → delete, unless it has
#   answers, in which case → 409
# ============================================================

class ExamSectionsBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, exam_id):
        exam, err = _get_exam_or_404(exam_id)
        if err:
            return err

        items = request.data.get("sections") or []
        if not isinstance(items, list):
            return Response(
                {"success": False, "message": "sections must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Validate everything first — no writes until all pass.
        validated = []
        for idx, item in enumerate(items):
            ser = ExamSectionWriteSerializer(data=item)
            if not ser.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": f"Invalid section {idx}",
                        "errors": ser.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            validated.append((idx, item, ser))

        # 2. Snapshot existing sections.
        existing_by_id = {str(s.id): s for s in exam.sections.all()}

        # 3. Decide which existing sections survive.
        incoming_ids = set()
        for _, item, _ in validated:
            rid = item.get("id")
            if _is_local_id(rid):
                continue
            rid_str = str(rid)
            if rid_str in existing_by_id:
                incoming_ids.add(rid_str)

        # 4. Delete removed sections — refuse if answered.
        to_delete = [
            s for sid, s in existing_by_id.items() if sid not in incoming_ids
        ]
        for section in to_delete:
            if _answers_for_section(section).exists():
                return Response(
                    {
                        "success": False,
                        "message": (
                            f'Cannot remove section "{section.title}": '
                            "candidates have already answered its questions."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        for section in to_delete:
            section.delete()

        # 5. Upsert in payload order.
        for order, (_, item, ser) in enumerate(validated):
            rid = item.get("id")
            section = (
                existing_by_id.get(str(rid))
                if not _is_local_id(rid)
                else None
            )

            if section is not None:
                section.title = ser.validated_data.get("title", section.title)
                section.kind = ser.validated_data.get("kind", section.kind)
                section.instructions = ser.validated_data.get(
                    "instructions", section.instructions
                )
                section.points_per_question = ser.validated_data.get(
                    "points_per_question", section.points_per_question
                )
                section.sort_order = order
                section.save()
            else:
                # Strip any client id; let Django assign a real one.
                payload = dict(ser.validated_data)
                payload.pop("id", None)
                ExamSection.objects.create(
                    exam=exam, sort_order=order, **payload
                )

        exam.refresh_from_db()
        return Response(
            {
                "success": True,
                "message": "Sections updated.",
                "data": ExamSerializer(exam).data,
            }
        )


# ============================================================
# QUESTIONS per SECTION — UPSERT
# POST /api/sections/<section_id>/questions/
#
# Body:
#   {
#     "questions": [
#       { "id": <uuid|null>, "type": "multiple-choice", ... },
#       ...
#     ]
#   }
#
# The frontend already calls this via
# examApi.saveSectionQuestions(sectionId, payload).
# ============================================================

class ExamSectionQuestionsBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, section_id):
        section, err = _get_section_or_404(section_id)
        if err:
            return err

        # Accept either {"questions": [...]} or a bare list.
        if isinstance(request.data, list):
            items = request.data
        else:
            items = request.data.get("questions")

        if items is None:
            items = []
        if not isinstance(items, list):
            return Response(
                {"success": False, "message": "questions must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Validate all first.
        validated = []
        for idx, item in enumerate(items):
            ser = ExamQuestionWriteSerializer(data=item)
            if not ser.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": f"Invalid question {idx}",
                        "errors": ser.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            validated.append((idx, item, ser))

        # 2. Snapshot existing questions.
        existing_by_id = {str(q.id): q for q in section.questions.all()}

        # 3. Surviving ids.
        incoming_ids = set()
        for _, item, _ in validated:
            rid = item.get("id")
            if _is_local_id(rid):
                continue
            rid_str = str(rid)
            if rid_str in existing_by_id:
                incoming_ids.add(rid_str)

        # 4. Delete removed questions — refuse if answered.
        to_delete = [
            q for qid, q in existing_by_id.items() if qid not in incoming_ids
        ]
        for question in to_delete:
            if _answers_for_question(question).exists():
                return Response(
                    {
                        "success": False,
                        "message": (
                            "Cannot remove a question that has already "
                            "been answered by a candidate."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        for question in to_delete:
            question.delete()

        # 5. Upsert.
        for order, (_, item, ser) in enumerate(validated):
            rid = item.get("id")
            question = (
                existing_by_id.get(str(rid))
                if not _is_local_id(rid)
                else None
            )

            if question is not None:
                ser.update(question, order=order)
            else:
                ser.create(section=section, order=order)

        section.refresh_from_db()
        return Response(
            {
                "success": True,
                "message": "Questions updated.",
                "data": ExamSectionWriteSerializer(section).data,
            }
        )