from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from judge.models.contest import ContestProblem, ContestParticipation
from judge.models.submission import Submission


class ExamQuestion(models.Model):
    """Multiple-choice metadata for a :class:`ContestProblem`."""

    CHOICES = (("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"))

    contest_problem = models.OneToOneField(
        ContestProblem,
        related_name="exam_question",
        on_delete=models.CASCADE,
        verbose_name=_("contest problem"),
    )
    prompt = models.TextField(blank=True, verbose_name=_("prompt"))
    correct_choice = models.CharField(
        max_length=1,
        choices=CHOICES,
        verbose_name=_("correct choice"),
    )

    class Meta:
        verbose_name = _("exam question")
        verbose_name_plural = _("exam questions")

    def __str__(self):
        return _("Exam question for %(problem)s") % {
            "problem": self.contest_problem.problem,
        }

    @property
    def label(self):
        return self.contest_problem.order


class ExamChoice(models.Model):
    question = models.ForeignKey(
        ExamQuestion,
        related_name="choices",
        on_delete=models.CASCADE,
        verbose_name=_("question"),
    )
    label = models.CharField(
        max_length=1,
        choices=ExamQuestion.CHOICES,
        verbose_name=_("label"),
    )
    text = models.TextField(verbose_name=_("choice text"))

    class Meta:
        verbose_name = _("exam choice")
        verbose_name_plural = _("exam choices")
        unique_together = ("question", "label")
        ordering = ["label"]

    def __str__(self):
        return _("Choice %(label)s for %(question)s") % {
            "label": self.label,
            "question": self.question,
        }


class ExamResponse(models.Model):
    question = models.ForeignKey(
        ExamQuestion,
        related_name="responses",
        on_delete=models.CASCADE,
        verbose_name=_("question"),
    )
    participation = models.ForeignKey(
        ContestParticipation,
        related_name="exam_responses",
        on_delete=models.CASCADE,
        verbose_name=_("participation"),
    )
    selected_choice = models.CharField(
        max_length=1,
        choices=ExamQuestion.CHOICES,
        verbose_name=_("selected choice"),
    )
    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="exam_response",
        verbose_name=_("submission"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        unique_together = ("question", "participation")
        verbose_name = _("exam response")
        verbose_name_plural = _("exam responses")

    def __str__(self):
        return _("Response for %(question)s by %(user)s") % {
            "question": self.question,
            "user": self.participation.user,
        }

    @property
    def is_correct(self):
        return self.selected_choice == self.question.correct_choice

    @property
    def points(self):
        return 1 if self.is_correct else 0

    @transaction.atomic
    def sync_contest_submission(self):
        from judge.models.contest import ContestSubmission
        from judge.models.runtime import Language

        contest_problem = self.question.contest_problem
        participation = self.participation
        now = timezone.now()
        points = float(self.points)
        result_code = "AC" if self.is_correct else "WA"

        if self.submission is None:
            submission = Submission.objects.create(
                user=participation.user,
                problem=contest_problem.problem,
                language=Language.get_default_language(),
                status="D",
                result=result_code,
                points=points,
                case_points=points,
                case_total=1.0,
                time=0,
                memory=0,
                judged_date=now,
                contest_object=participation.contest,
            )
            submission.date = now
            submission.save(update_fields=["date"])
            self.submission = submission
            self.save(update_fields=["submission"])
        else:
            submission = self.submission
            submission.user = participation.user
            submission.problem = contest_problem.problem
            if submission.language_id is None:
                submission.language = Language.get_default_language()
            submission.status = "D"
            submission.result = result_code
            submission.points = points
            submission.case_points = points
            submission.case_total = 1.0
            submission.time = 0
            submission.memory = 0
            submission.judged_date = now
            submission.contest_object = participation.contest
            submission.date = now
            submission.save()

        contest_submission, _ = ContestSubmission.objects.get_or_create(
            submission=submission,
            defaults={
                "problem": contest_problem,
                "participation": participation,
            },
        )

        changed = False
        if contest_submission.problem_id != contest_problem.id:
            contest_submission.problem = contest_problem
            changed = True
        if contest_submission.participation_id != participation.id:
            contest_submission.participation = participation
            changed = True
        if contest_submission.points != points:
            contest_submission.points = points
            changed = True
        if contest_submission.is_pretest:
            contest_submission.is_pretest = False
            changed = True

        if changed:
            contest_submission.save()

        return contest_submission

    @classmethod
    def record_answer(cls, participation, question, choice):
        with transaction.atomic():
            response, created = cls.objects.select_for_update().get_or_create(
                question=question,
                participation=participation,
                defaults={"selected_choice": choice},
            )
            if not created and response.selected_choice != choice:
                response.selected_choice = choice
                response.save(update_fields=["selected_choice"])
            response.sync_contest_submission()
        return response
