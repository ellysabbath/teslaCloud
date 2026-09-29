# questions/serializers.py

from rest_framework import serializers

from .models import (
    Question,
    QuestionOption,
    QuestionBooleanAnswer,
    MatchingColumnA,
    MatchingColumnB,
    MatchingScheme,
    FillBlankAnswer,
)


# ============================================================
# READ — used when loading an exam
# ============================================================
class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "option_text", "is_correct", "sort_order"]


class MatchingColumnASerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchingColumnA
        fields = ["id", "item_text", "sort_order"]


class MatchingColumnBSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchingColumnB
        fields = ["id", "item_text", "sort_order"]


class FillBlankAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FillBlankAnswer
        fields = ["id", "answer_text", "is_primary"]


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)
    boolean = serializers.SerializerMethodField()
    column_a = MatchingColumnASerializer(
        source="matching_column_a", many=True, read_only=True
    )
    column_b = MatchingColumnBSerializer(
        source="matching_column_b", many=True, read_only=True
    )
    correct_matches = serializers.SerializerMethodField()
    fill_blank = FillBlankAnswerSerializer(
        source="fill_blank_answers", many=True, read_only=True
    )

    class Meta:
        model = Question
        fields = [
            "id",
            "type",
            "text",
            "sort_order",
            "options",
            "boolean",
            "column_a",
            "column_b",
            "correct_matches",
            "fill_blank",
        ]

    def get_boolean(self, obj):
        try:
            return obj.boolean_answer.correct_value
        except QuestionBooleanAnswer.DoesNotExist:
            return None

    def get_correct_matches(self, obj):
        """
        Return the correct matching scheme as ``{ "aIndex": "bIndex" }``.

        The source of truth is ``Question.correct_matches`` — a JSONField
        written by ``SectionQuestionsBulkView`` when the admin saves.
        If for some reason the JSONField is empty (legacy data), fall
        back to the old ``MatchingScheme`` table and convert the UUIDs
        to indices so the frontend always sees the same shape.
        """
        stored = dict(obj.correct_matches or {})
        if stored:
            return {str(k): str(v) for k, v in stored.items()}

        # Legacy fallback — read MatchingScheme rows and convert to indices.
        a_rows = list(obj.matching_column_a.all().order_by("sort_order"))
        b_rows = list(obj.matching_column_b.all().order_by("sort_order"))
        a_index = {str(r.id): i for i, r in enumerate(a_rows)}
        b_index = {str(r.id): i for i, r in enumerate(b_rows)}

        out = {}
        for row in obj.matching_scheme.all():
            a_idx = a_index.get(str(row.column_a_id))
            b_idx = b_index.get(str(row.column_b_id))
            if a_idx is not None and b_idx is not None:
                out[str(a_idx)] = str(b_idx)
        return out


# ============================================================
# WRITE — accepts the frontend's payload
# ============================================================
class QuestionWriteSerializer(serializers.Serializer):
    """
    One item per question, matching the frontend ExamQuestion shape:

    - multiple-choice: { type, text, options, correctOptionIndex }
    - true-false:      { type, text, correctBoolean }
    - matching:        { type, text, columnA, columnB, correctMatches }
    - fill-blank:      { type, text, correctText, acceptAlternatives }
    """
    type = serializers.CharField()
    text = serializers.CharField(allow_blank=True, required=False)
    options = serializers.ListField(
        child=serializers.CharField(allow_blank=True), required=False
    )
    correctOptionIndex = serializers.IntegerField(required=False)
    correctBoolean = serializers.BooleanField(required=False)
    columnA = serializers.ListField(required=False)
    columnB = serializers.ListField(required=False)
    correctMatches = serializers.DictField(required=False)
    correctText = serializers.CharField(allow_blank=True, required=False)
    acceptAlternatives = serializers.ListField(required=False)