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
# READ serializer — used when loading an exam
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
        scheme = obj.matching_scheme.all()
        return {str(row.column_a_id): str(row.column_b_id) for row in scheme}


# ============================================================
# WRITE serializer — accepts the frontend's payload
# ============================================================
class QuestionWriteSerializer(serializers.Serializer):
    """
    One item per question, matching the frontend ExamQuestion shape:

    - multiple-choice:
        { type: 'multiple-choice', text, options: [..], correctOptionIndex: 0 }
    - true-false:
        { type: 'true-false', text, correctBoolean: true }
    - matching:
        { type: 'matching', text, columnA:[{id,text}], columnB:[{id,text}], correctMatches:{aId:bId} }
    - fill-blank:
        { type: 'fill-blank', text, correctText, acceptAlternatives: [] }
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