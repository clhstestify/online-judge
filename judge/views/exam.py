from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import FormView

from judge.forms import ExamSheetForm
from judge.models import Contest, ContestParticipation, ExamQuestion, ExamResponse
from judge.utils.views import generic_message


class ContestExamView(LoginRequiredMixin, FormView):
    template_name = "exam/take.html"
    form_class = ExamSheetForm

    def dispatch(self, request, *args, **kwargs):
        self.contest = get_object_or_404(Contest, key=kwargs["contest"])
        if self.contest.format_name != "thptqg":
            raise PermissionDenied

        try:
            self.participation = self.get_participation()
        except ContestParticipation.DoesNotExist:
            return generic_message(
                request,
                _("Join required"),
                _("You need to join this contest to access the exam."),
            )

        self.paper = getattr(self.contest, "exam_paper", None)
        if not self.paper:
            return generic_message(
                request,
                _("Exam not configured"),
                _("This contest does not have an exam paper yet."),
            )

        self.questions = list(
            self.paper.questions.select_related("paper")
            .prefetch_related("choices")
            .order_by("part", "number")
        )
        if not self.questions:
            return generic_message(
                request,
                _("No exam questions"),
                _("This contest does not have any configured exam questions."),
            )

        return super().dispatch(request, *args, **kwargs)

    def get_participation(self):
        profile = getattr(self.request, "profile", None)
        if profile is None:
            raise PermissionDenied

        participation = getattr(self.request, "participation", None)
        if (
            participation
            and participation.contest_id == self.contest.id
            and participation.user_id == profile.id
        ):
            return participation

        return ContestParticipation.objects.get(
            contest=self.contest,
            user=profile,
            virtual__in=[
                ContestParticipation.LIVE,
                ContestParticipation.SPECTATE,
            ],
        )

    def get_responses(self):
        if not hasattr(self, "_responses"):
            self._responses = {
                response.question_id: response
                for response in ExamResponse.objects.filter(
                    participation=self.participation,
                    question__paper=self.paper,
                ).select_related("selected_choice")
            }
        return self._responses

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "paper": self.paper,
                "questions": self.questions,
                "responses": self.get_responses(),
            }
        )
        return kwargs

    def form_valid(self, form):
        responses = self.get_responses()
        updated = False

        # Part I – multiple choice
        for question, field_name in form.multiple_choice_field_map:
            choice_key = form.cleaned_data.get(field_name)
            existing = responses.get(question.id)
            if not choice_key and existing is None:
                continue
            response = existing or ExamResponse(
                question=question, participation=self.participation
            )
            selected_choice = None
            if choice_key:
                selected_choice = form.choice_lookup.get(question.id, {}).get(choice_key)
            response.selected_choice = selected_choice
            response.true_false_answers = {}
            response.short_answer_text = ""
            response.save(recompute=False)
            responses[question.id] = response
            updated = True

        # Part II – True/False statements
        for question, entries in form.true_false_field_map.items():
            answers = {}
            has_value = False
            for choice, field_name in entries:
                value = form.cleaned_data.get(field_name)
                if value in {"true", "false"}:
                    answers[str(choice.id)] = value == "true"
                    has_value = True
            existing = responses.get(question.id)
            if existing is None and not has_value:
                continue
            response = existing or ExamResponse(
                question=question, participation=self.participation
            )
            response.true_false_answers = answers
            response.selected_choice = None
            response.short_answer_text = ""
            response.save(recompute=False)
            responses[question.id] = response
            updated = True

        # Part III – short answers
        for question, field_name in form.short_answer_field_map:
            value = form.cleaned_data.get(field_name, "")
            value = (value or "").strip()
            existing = responses.get(question.id)
            if not value and existing is None:
                continue
            response = existing or ExamResponse(
                question=question, participation=self.participation
            )
            response.short_answer_text = value
            response.selected_choice = None
            response.true_false_answers = {}
            response.save(recompute=False)
            responses[question.id] = response
            updated = True

        if updated:
            self.participation.recompute_results()

        messages.success(self.request, _("Your answers have been saved."))

        if "finish" in self.request.POST:
            return redirect("contest_ranking", contest=self.contest.key)

        return super().form_valid(form)

    def get_success_url(self):
        return reverse("contest_exam", kwargs={"contest": self.contest.key})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        context.update(
            {
                "contest": self.contest,
                "participation": self.participation,
                "paper": self.paper,
                "part1_questions": form.part1_questions if form else [],
                "part2_questions": form.part2_questions if form else [],
                "part3_questions": form.part3_questions if form else [],
                "has_part3": bool(self.paper.part3_questions),
                "responses": self.get_responses(),
                "part_counts": {
                    "part1": self.paper.part1_questions,
                    "part2": self.paper.part2_questions,
                    "part3": self.paper.part3_questions,
                },
                "part_points": {
                    "part1": self.paper.part1_point_value,
                    "part2": self.paper.part2_point_value,
                    "part3": self.paper.part3_point_value,
                },
            }
        )
        return context
