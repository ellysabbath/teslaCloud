# questions/views.py

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
# POST /api/exams/sections/<section_id>/questions/save/
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

                # Build Column A rows, remember UUID -> index.
                a_index_by_uuid = {}
                for ai, a in enumerate(colA_raw):
                    text = a.get("text") if isinstance(a, dict) else str(a)
                    MatchingColumnA.objects.create(
                        question=question,
                        item_text=text or "",
                        sort_order=ai,
                    )
                    client_id = (
                        a.get("id") if isinstance(a, dict) else None
                    )
                    if client_id:
                        a_index_by_uuid[str(client_id)] = ai

                # Build Column B rows, remember UUID -> index.
                b_index_by_uuid = {}
                for bi, b in enumerate(colB_raw):
                    text = b.get("text") if isinstance(b, dict) else str(b)
                    MatchingColumnB.objects.create(
                        question=question,
                        item_text=text or "",
                        sort_order=bi,
                    )
                    client_id = (
                        b.get("id") if isinstance(b, dict) else None
                    )
                    if client_id:
                        b_index_by_uuid[str(client_id)] = bi

                # Convert correctMatches to index → index strings.
                # The frontend may send either UUID keys or index keys.
                idx_matches = {}
                for a_key, b_key in matches.items():
                    a_str = str(a_key)
                    b_str = str(b_key)

                    if a_str.isdigit() and b_str.isdigit():
                        idx_matches[a_str] = b_str
                        continue

                    a_idx = a_index_by_uuid.get(a_str)
                    b_idx = b_index_by_uuid.get(b_str)
                    if a_idx is not None and b_idx is not None:
                        idx_matches[str(a_idx)] = str(b_idx)

                # Persist on Question.correct_matches — the source of
                # truth that _auto_mark reads.
                question.correct_matches = idx_matches
                question.save(update_fields=["correct_matches"])

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