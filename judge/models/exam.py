from __future__ import annotations

import os
from typing import Dict, Iterable, List, Tuple

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField


def exam_pdf_upload_to(instance: "ExamPaper", filename: str) -> str:
    contest_key = instance.contest.key if instance.contest_id else "contest"
    return os.path.join("exam_papers", contest_key, filename)


class ExamPaper(models.Model):
    SUBJECT_MATH = "math"
    SUBJECT_PHYSICS = "physics"
    SUBJECT_CHEMISTRY = "chemistry"
    SUBJECT_BIOLOGY = "biology"
    SUBJECT_HISTORY = "history"
    SUBJECT_GEOGRAPHY = "geography"
    SUBJECT_CIVIC = "civic_education"
    SUBJECT_ENGLISH = "english"
    SUBJECT_FOREIGN_LANGUAGE = "foreign_language"

    SUBJECT_CHOICES = (
        (SUBJECT_MATH, _("Mathematics")),
        (SUBJECT_PHYSICS, _("Physics")),
        (SUBJECT_CHEMISTRY, _("Chemistry")),
        (SUBJECT_BIOLOGY, _("Biology")),
        (SUBJECT_HISTORY, _("History")),
        (SUBJECT_GEOGRAPHY, _("Geography")),
        (SUBJECT_CIVIC, _("Civic education")),
        (SUBJECT_ENGLISH, _("English")),
        (SUBJECT_FOREIGN_LANGUAGE, _("Other foreign language")),
    )

    contest = models.OneToOneField(
        "judge.Contest",
        related_name="exam_paper",
        on_delete=models.CASCADE,
        verbose_name=_("contest"),
    )
    subject = models.CharField(max_length=32, choices=SUBJECT_CHOICES)
    part1_questions = models.PositiveIntegerField(
        default=40, verbose_name=_("part I questions")
    )
    part2_questions = models.PositiveIntegerField(
        default=8, verbose_name=_("part II questions")
    )
    part3_questions = models.PositiveIntegerField(
        default=6, verbose_name=_("part III questions")
    )
    pdf = models.FileField(
        upload_to=exam_pdf_upload_to,
        blank=True,
        null=True,
        verbose_name=_("exam PDF"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("exam paper")
        verbose_name_plural = _("exam papers")

    def __str__(self) -> str:
        return f"{self.contest.name} – {self.get_subject_display()}"

    @property
    def part1_point_value(self) -> float:
        return 0.25

    @property
    def part2_point_value(self) -> float:
        return 1.0

    @property
    def part3_point_value(self) -> float:
        return 0.5 if self.subject == self.SUBJECT_MATH else 0.25

    @property
    def true_false_items(self) -> int:
        return 4

    def questions_for_part(self, part: str) -> Iterable["ExamQuestion"]:
        return self.questions.filter(part=part).order_by("number")

    def max_points_by_part(self) -> Dict[str, float]:
        return {
            "part1": self.part1_questions * self.part1_point_value,
            "part2": self.part2_questions * self.part2_point_value,
            "part3": self.part3_questions * self.part3_point_value,
        }

    def total_max_points(self) -> float:
        values = self.max_points_by_part()
        return sum(values.values())

    def export_answers(self) -> Dict[str, List[str]]:
        data: Dict[str, List] = {"part1": [], "part2": [], "part3": []}
        for question in self.questions.select_related(None).prefetch_related("choices").order_by(
            "part", "number"
        ):
            if question.part == ExamQuestion.PART_MULTIPLE_CHOICE:
                choice = question.choices.filter(is_correct=True).first()
                data["part1"].append(choice.key.upper() if choice else "")
            elif question.part == ExamQuestion.PART_TRUE_FALSE:
                ordered_choices = list(question.choices.order_by("key"))
                values = [bool(c.is_correct) for c in ordered_choices]
                data["part2"].append(values)
            elif question.part == ExamQuestion.PART_SHORT_ANSWER:
                data["part3"].append(question.short_answer or "")
        return data

    def sync_from_answer_data(self, answers: Dict[str, List]) -> None:
        part1 = answers.get("part1", [])
        part2 = answers.get("part2", [])
        part3 = answers.get("part3", [])

        with transaction.atomic():
            self.questions.all().delete()

            self.part1_questions = len(part1)
            self.part2_questions = len(part2)
            self.part3_questions = len(part3)
            self.save(
                update_fields=[
                    "part1_questions",
                    "part2_questions",
                    "part3_questions",
                    "updated_at",
                ]
            )

            for index, correct in enumerate(part1, start=1):
                question = ExamQuestion.objects.create(
                    paper=self,
                    part=ExamQuestion.PART_MULTIPLE_CHOICE,
                    number=index,
                    prompt=f"Phần I – Câu {index}",
                    max_points=self.part1_point_value,
                )
                for option in ("A", "B", "C", "D"):
                    ExamChoice.objects.create(
                        question=question,
                        key=option,
                        is_correct=option == correct,
                    )

            for index, statement_answers in enumerate(part2, start=1):
                question = ExamQuestion.objects.create(
                    paper=self,
                    part=ExamQuestion.PART_TRUE_FALSE,
                    number=index,
                    prompt=f"Phần II – Câu {index}",
                    max_points=self.part2_point_value,
                )
                for offset, value in enumerate(statement_answers):
                    label = chr(ord("a") + offset)
                    ExamChoice.objects.create(
                        question=question,
                        key=label,
                        is_correct=bool(value),
                    )

            for index, answer in enumerate(part3, start=1):
                ExamQuestion.objects.create(
                    paper=self,
                    part=ExamQuestion.PART_SHORT_ANSWER,
                    number=index,
                    prompt=f"Phần III – Câu {index}",
                    max_points=self.part3_point_value,
                    short_answer=str(answer or "").strip(),
                )


class ExamQuestion(models.Model):
    PART_MULTIPLE_CHOICE = "multiple_choice"
    PART_TRUE_FALSE = "true_false"
    PART_SHORT_ANSWER = "short_answer"
    PART_CHOICES = (
        (PART_MULTIPLE_CHOICE, _("Multiple choice")),
        (PART_TRUE_FALSE, _("True/False")),
        (PART_SHORT_ANSWER, _("Short answer")),
    )

    contest_problem = models.OneToOneField(
        "judge.ContestProblem",
        on_delete=models.CASCADE,
        related_name="exam_question",
        verbose_name=_("contest problem"),
        null=True,
        blank=True,
    )
    paper = models.ForeignKey(
        ExamPaper,
        related_name="questions",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("exam paper"),
    )
    part = models.CharField(max_length=32, choices=PART_CHOICES)
    number = models.PositiveIntegerField(default=1)
    prompt = models.TextField(verbose_name=_("question prompt"), blank=True)
    max_points = models.FloatField(default=0.25)
    short_answer = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_("short answer"),
        help_text=_("Expected answer for short-answer questions."),
    )

    class Meta:
        verbose_name = _("exam question")
        verbose_name_plural = _("exam questions")
        ordering = ["paper_id", "part", "number"]
        unique_together = ("paper", "part", "number")

    def __str__(self) -> str:
        if self.paper:
            return f"{self.paper} – {self.get_part_display()} #{self.number}"
        if self.contest_problem:
            return f"{self.contest_problem} ({self.get_part_display()})"
        return f"{self.get_part_display()} #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.max_points:
            if self.part == self.PART_TRUE_FALSE:
                self.max_points = 1.0
            elif self.part == self.PART_SHORT_ANSWER:
                if self.paper:
                    self.max_points = self.paper.part3_point_value
                else:
                    self.max_points = 0.25
            else:
                self.max_points = 0.25
        super().save(*args, **kwargs)

    @property
    def total_items(self) -> int:
        if self.part == self.PART_TRUE_FALSE:
            return self.choices.count()
        return 1

    def default_max_points(self) -> float:
        if self.part == self.PART_TRUE_FALSE:
            return 1.0
        if self.part == self.PART_SHORT_ANSWER:
            return self.max_points or 0.25
        return 0.25

    def get_true_false_points(self, correct: int) -> float:
        """Return the awarded points for a True/False question."""
        score_map = {1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}
        base = score_map.get(correct, 0)
        return round(base * (self.max_points or 1.0), 3)

    @staticmethod
    def normalize_short_answer(value: str) -> str:
        return (value or "").strip().lower()


class ExamChoice(models.Model):
    question = models.ForeignKey(
        ExamQuestion,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name=_("question"),
    )
    key = models.CharField(max_length=16, verbose_name=_("label"))
    text = models.TextField(blank=True, verbose_name=_("text"))
    is_correct = models.BooleanField(default=False, verbose_name=_("is correct"))

    class Meta:
        verbose_name = _("exam choice")
        verbose_name_plural = _("exam choices")
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key}: {self.text[:30]}"


class ExamResponse(models.Model):
    question = models.ForeignKey(
        ExamQuestion,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name=_("question"),
    )
    participation = models.ForeignKey(
        "judge.ContestParticipation",
        on_delete=models.CASCADE,
        related_name="exam_responses",
        verbose_name=_("participation"),
    )
    selected_choice = models.ForeignKey(
        ExamChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses",
        verbose_name=_("selected choice"),
    )
    true_false_answers = JSONField(blank=True, null=True)
    short_answer_text = models.CharField(max_length=64, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    points = models.FloatField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("question", "participation")
        verbose_name = _("exam response")
        verbose_name_plural = _("exam responses")

    def __str__(self) -> str:
        return f"Response of {self.participation} to {self.question}"

    def _grade_multiple_choice(self) -> Tuple[int, int, float]:
        total = 1
        correct = 0
        if self.selected_choice and self.selected_choice.is_correct:
            correct = 1
            return correct, total, self.question.max_points or 0.25
        return correct, total, 0.0

    def _grade_true_false(self) -> Tuple[int, int, float]:
        answers: Dict[str, bool] = {}
        if isinstance(self.true_false_answers, dict):
            answers = {str(k): bool(v) for k, v in self.true_false_answers.items()}
        total = self.question.total_items or 4
        correct = 0
        for choice in self.question.choices.all():
            user_answer = answers.get(str(choice.id))
            if user_answer is None:
                continue
            if bool(user_answer) == bool(choice.is_correct):
                correct += 1
        points = self.question.get_true_false_points(correct)
        return correct, total, points

    def _grade_short_answer(self) -> Tuple[int, int, float]:
        total = 1
        correct = 0
        expected = ExamQuestion.normalize_short_answer(self.question.short_answer)
        given = ExamQuestion.normalize_short_answer(self.short_answer_text)
        if expected and given and expected == given:
            correct = 1
            return correct, total, self.question.max_points or 0.25
        return correct, total, 0.0

    def grade(self) -> Tuple[int, int, float]:
        if self.question.part == ExamQuestion.PART_MULTIPLE_CHOICE:
            return self._grade_multiple_choice()
        if self.question.part == ExamQuestion.PART_TRUE_FALSE:
            return self._grade_true_false()
        if self.question.part == ExamQuestion.PART_SHORT_ANSWER:
            return self._grade_short_answer()
        return 0, 0, 0.0

    def save(self, *args, **kwargs):
        recompute = kwargs.pop("recompute", True)
        self.submitted_at = timezone.now()
        correct, total, points = self.grade()
        self.correct_count = correct
        self.total_count = total
        self.points = round(points, 3)
        super().save(*args, **kwargs)
        if recompute:
            self.participation.recompute_results()
