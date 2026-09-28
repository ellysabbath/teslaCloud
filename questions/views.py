from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exams.models import ExamSection

from .models import (
    Question,
    QuestionOption,
    QuestionBooleanAnswer,
    MatchingColumnA,
    MatchingColumnB,
    MatchingScheme,
    FillBlankAnswer,
)
from .serializers import QuestionSerializer, QuestionWriteSerializer


# ============================================================
# GET /api/exams/sections/<section_id>/questions/
# Returns every question in a section (with nested options, columns, etc.).
# ============================================================
class SectionQuestionsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, section_id):
        try:
            section = ExamSection.objects.get(id=section_id)
        except ExamSection.DoesNotExist:
            return Response(
                {"success": False, "message": "Section not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = (
            section.questions
            .all()
            .prefetch_related(
                "options",
                "matching_column_a",
                "matching_column_b",
                "matching_scheme",
                "fill_blank_answers",
            )
            .order_by("sort_order")
        )
        return Response(
            {"success": True, "data": QuestionSerializer(qs, many=True).data}
        )


# ============================================================
# POST /api/exams/sections/<section_id>/questions/
# Replaces all questions in a section.
# ============================================================
class SectionQuestionsBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, section_id):
        try:
            section = ExamSection.objects.get(id=section_id)
        except ExamSection.DoesNotExist:
            return Response(
                {"success": False, "message": "Section not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        items = request.data.get("questions") or []
        if not isinstance(items, list):
            return Response(
                {"success": False, "message": "questions must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------- Validate all before touching the DB ----------
        validated = []
        for idx, raw in enumerate(items):
            ser = QuestionWriteSerializer(data=raw)
            if not ser.is_valid():
                return Response(
                    {
                        "success": False,
                        "message": f"Invalid question {idx + 1}",
                        "errors": ser.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            validated.append(ser.validated_data)

        # ---------- Replace ----------
        section.questions.all().delete()

        for idx, q in enumerate(validated):
            question = Question.objects.create(
                section=section,
                type=q["type"],
                text=q.get("text") or "",
                sort_order=idx,
            )

            qtype = q["type"]

            # ---------- Multiple choice ----------
            if qtype == "multiple-choice":
                opts = q.get("options") or []
                correct_idx = q.get("correctOptionIndex", 0)
                for oi, text in enumerate(opts):
                    QuestionOption.objects.create(
                        question=question,
                        option_text=text or "",
                        is_correct=(oi == correct_idx),
                        sort_order=oi,
                    )

            # ---------- True / False ----------
            elif qtype == "true-false":
                QuestionBooleanAnswer.objects.create(
                    question=question,
                    correct_value=bool(q.get("correctBoolean", True)),
                )

            # ---------- Matching ----------
            elif qtype == "matching":
                colA_raw = q.get("columnA") or []
                colB_raw = q.get("columnB") or []
                matches = q.get("correctMatches") or {}

                a_id_map = {}
                for ai, a in enumerate(colA_raw):
                    a_obj = MatchingColumnA.objects.create(
                        question=question,
                        item_text=a.get("text") or "",
                        sort_order=ai,
                    )
                    a_id_map[str(a.get("id"))] = a_obj

                b_id_map = {}
                for bi, b in enumerate(colB_raw):
                    b_obj = MatchingColumnB.objects.create(
                        question=question,
                        item_text=b.get("text") or "",
                        sort_order=bi,
                    )
                    b_id_map[str(b.get("id"))] = b_obj

                for a_key, b_key in matches.items():
                    a_obj = a_id_map.get(str(a_key))
                    b_obj = b_id_map.get(str(b_key))
                    if a_obj and b_obj:
                        MatchingScheme.objects.create(
                            question=question,
                            column_a=a_obj,
                            column_b=b_obj,
                        )

            # ---------- Fill-in-the-blank ----------
            elif qtype == "fill-blank":
                primary = (q.get("correctText") or "").strip()
                if primary:
                    FillBlankAnswer.objects.create(
                        question=question,
                        answer_text=primary,
                        is_primary=True,
                    )
                for alt in q.get("acceptAlternatives") or []:
                    alt = (alt or "").strip()
                    if alt:
                        FillBlankAnswer.objects.create(
                            question=question,
                            answer_text=alt,
                            is_primary=False,
                        )

        return Response(
            {
                "success": True,
                "message": f"Saved {len(validated)} questions.",
                "data": {"count": len(validated)},
            }
        )