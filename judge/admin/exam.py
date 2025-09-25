from __future__ import annotations

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from judge.models import ExamPaper
from judge.utils.exam_import import (
    extract_answer_text,
    parse_answer_document,
    parse_part1_lines,
    parse_part2_lines,
    parse_part3_lines,
)


class ExamPaperAdminForm(forms.ModelForm):
    manual_part1 = forms.CharField(
        label=_("Manual part I answers"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("One question per line, e.g. \"1. A\"."),
    )
    manual_part2 = forms.CharField(
        label=_("Manual part II answers"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("Use Đ for true and S for false, e.g. \"1. Đ S S Đ\"."),
    )
    manual_part3 = forms.CharField(
        label=_("Manual part III answers"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("One short answer per line, e.g. \"1. 12345\"."),
    )
    answer_file = forms.FileField(
        label=_("Upload answer file"),
        required=False,
        help_text=_(
            "Accepted .docx or .pdf with sections [PART1], [PART2], [PART3]. "
            "Example: [PART1]\\n1. A\\n…"
        ),
    )

    class Meta:
        model = ExamPaper
        fields = (
            "contest",
            "code",
            "subject",
            "part1_questions",
            "part2_questions",
            "part3_questions",
            "pdf",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            answers = self.instance.export_answers()
            if answers["part1"]:
                self.fields["manual_part1"].initial = self._format_part1(answers["part1"])
            if answers["part2"]:
                self.fields["manual_part2"].initial = self._format_part2(answers["part2"])
            if answers["part3"]:
                self.fields["manual_part3"].initial = self._format_part3(answers["part3"])

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not code:
            raise ValidationError(_("Exam code is required."))
        return code

    @staticmethod
    def _format_part1(answers):
        return "\n".join(f"{index}. {value}" for index, value in enumerate(answers, start=1))

    @staticmethod
    def _format_part2(answers):
        lines = []
        for index, values in enumerate(answers, start=1):
            tokens = ["Đ" if value else "S" for value in values]
            lines.append(f"{index}. {' '.join(tokens)}")
        return "\n".join(lines)

    @staticmethod
    def _format_part3(answers):
        return "\n".join(f"{index}. {value}" for index, value in enumerate(answers, start=1))

    def clean(self):
        cleaned = super().clean()
        answer_file = cleaned.get("answer_file")
        manual_values = (
            cleaned.get("manual_part1"),
            cleaned.get("manual_part2"),
            cleaned.get("manual_part3"),
        )
        has_manual = any(value for value in manual_values)

        if answer_file and has_manual:
            raise ValidationError(
                _("Choose either manual answers or an uploaded file, not both."),
            )

        parsed_answers = {}

        try:
            if answer_file:
                text = extract_answer_text(answer_file)
                answer_file.seek(0)
                parsed = parse_answer_document(text)
                parsed_answers = {k: v for k, v in parsed.items() if v is not None}
            elif has_manual:
                if cleaned.get("manual_part1"):
                    parsed_answers["part1"] = parse_part1_lines(
                        cleaned["manual_part1"].splitlines()
                    )
                if cleaned.get("manual_part2"):
                    parsed_answers["part2"] = parse_part2_lines(
                        cleaned["manual_part2"].splitlines()
                    )
                if cleaned.get("manual_part3"):
                    parsed_answers["part3"] = parse_part3_lines(
                        cleaned["manual_part3"].splitlines()
                    )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        cleaned["parsed_answers"] = parsed_answers or None
        return cleaned


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    form = ExamPaperAdminForm
    list_display = (
        "contest",
        "code",
        "subject",
        "part1_questions",
        "part2_questions",
        "part3_questions",
    )
    search_fields = ("contest__name", "contest__key", "code")
    list_select_related = ("contest",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "contest",
                    "code",
                    "subject",
                    "pdf",
                    "part1_questions",
                    "part2_questions",
                    "part3_questions",
                )
            },
        ),
        (
            _("Answer key"),
            {
                "fields": (
                    "manual_part1",
                    "manual_part2",
                    "manual_part3",
                    "answer_file",
                )
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        parsed = form.cleaned_data.get("parsed_answers")
        if parsed:
            current = obj.export_answers()
            data = {
                "part1": parsed.get("part1", current.get("part1", [])),
                "part2": parsed.get("part2", current.get("part2", [])),
                "part3": parsed.get("part3", current.get("part3", [])),
            }
            obj.sync_from_answer_data(data)
