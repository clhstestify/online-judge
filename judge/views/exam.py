import random

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
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

        self.paper = self._get_or_assign_paper()
        if not self.paper:
            return generic_message(
                request,
                _("Exam not configured"),
                _("This contest does not have an exam paper yet."),
            )

        self.exam_read_only = bool(
            self.participation.exam_locked or self.participation.exam_finalized_at
        )
        if self.should_show_results():
            self.exam_read_only = True

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

        return (
            ContestParticipation.objects.select_related("assigned_exam_paper")
            .filter(
                contest=self.contest,
                user=profile,
                virtual__in=[
                    ContestParticipation.LIVE,
                    ContestParticipation.SPECTATE,
                ],
            )
            .get()
        )

    def _get_or_assign_paper(self):
        paper = self.participation.assigned_exam_paper
        if paper and paper.contest_id == self.contest.id:
            return paper

        papers = list(self.contest.exam_papers.all())
        if not papers:
            return None

        paper = random.choice(papers)
        ContestParticipation.objects.filter(pk=self.participation.pk).update(
            assigned_exam_paper=paper
        )
        self.participation.assigned_exam_paper = paper
        return paper

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
                "read_only": self.exam_read_only,
            }
        )
        return kwargs

    def form_valid(self, form):
        if self.should_show_results():
            messages.info(
                self.request,
                _("The contest has ended. Exam answers are read-only."),
            )
            return redirect(self.get_success_url())

        if self.participation.exam_locked:
            messages.error(
                self.request,
                _("Your exam session has been locked due to violations."),
            )
            return redirect(self.get_success_url())

        if self.participation.exam_finalized_at:
            messages.info(
                self.request,
                _("You have already submitted your exam."),
            )
            return redirect(self.get_success_url())

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
            if not self.participation.exam_finalized_at:
                self.participation.exam_finalized_at = timezone.now()
                self.participation.save(update_fields=["exam_finalized_at"])
            messages.success(self.request, _("Your exam has been submitted."))
            return redirect("contest_ranking", contest=self.contest.key)

        return super().form_valid(form)

    def get_success_url(self):
        return reverse("contest_exam", kwargs={"contest": self.contest.key})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("form")
        show_results = self.should_show_results()
        overview, feedback = self.build_question_overview(show_results)
        context.update(
            {
                "contest": self.contest,
                "participation": self.participation,
                "paper": self.paper,
                "assigned_paper": self.paper,
                "exam_code": self.paper.code,
                "exam_locked": self.participation.exam_locked,
                "exam_finalized": bool(self.participation.exam_finalized_at),
                "exam_read_only": self.exam_read_only,
                "violation_count": self.participation.exam_violation_count,
                "violation_limit": 5,
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
                "show_exam_results": show_results,
                "question_overview": overview,
                "question_feedback": feedback,
            }
        )
        return context

    def should_show_results(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.has_perm("judge.change_contest"):
            return True
        return self.contest.ended

    def build_question_overview(self, show_results):
        responses = self.get_responses()
        overview = {
            "part1": [],
            "part2": [],
            "part3": [],
        }
        feedback = {}
        for question in self.questions:
            response = responses.get(question.id)
            detail = self._build_question_feedback(question, response, show_results)
            feedback[question.id] = detail
            part_key = detail.get("part_key")
            anchor = f"#question-{part_key}-{question.number}"
            if question.part == ExamQuestion.PART_TRUE_FALSE:
                for statement in detail.get("statements", []):
                    overview["part2"].append(
                        {
                            "label": f"{question.number}{statement['key'].lower()}",
                            "url": anchor,
                            "status": statement.get("status", "unanswered"),
                            "tooltip": self._build_nav_tooltip(
                                statement.get("status_label"),
                                statement.get("user_display"),
                                statement.get("correct_display"),
                                show_results,
                            ),
                        }
                    )
            else:
                overview[part_key].append(
                    {
                        "label": str(question.number),
                        "url": anchor,
                        "status": detail.get("status", "unanswered"),
                        "tooltip": self._build_nav_tooltip(
                            detail.get("result_label"),
                            detail.get("user_display"),
                            detail.get("correct_display"),
                            show_results,
                        ),
                    }
                )

        sections = []
        part_labels = {
            "part1": _("Part I"),
            "part2": _("Part II"),
            "part3": _("Part III"),
        }
        for key in ("part1", "part2", "part3"):
            if key == "part3" and not self.paper.part3_questions:
                continue
            sections.append(
                {
                    "key": key,
                    "title": part_labels.get(key, key.title()),
                    "entries": overview.get(key, []),
                }
            )
        return sections, feedback

    def _build_question_feedback(self, question, response, show_results):
        detail = {
            "part_key": self._get_part_key(question.part),
            "status": "unanswered",
            "answered": False,
            "user_display": _("No answer"),
            "correct_display": _("Not provided"),
            "result_label": _("No answer"),
        }

        if question.part == ExamQuestion.PART_MULTIPLE_CHOICE:
            return self._feedback_multiple_choice(question, response, show_results, detail)
        if question.part == ExamQuestion.PART_TRUE_FALSE:
            return self._feedback_true_false(question, response, show_results, detail)
        if question.part == ExamQuestion.PART_SHORT_ANSWER:
            return self._feedback_short_answer(question, response, show_results, detail)
        return detail

    def _feedback_multiple_choice(self, question, response, show_results, detail):
        correct_choices = [
            choice.key.upper()
            for choice in question.choices.order_by("key")
            if choice.is_correct
        ]
        correct_display = ", ".join(correct_choices) if correct_choices else _("Not provided")
        selected = None
        if response and response.selected_choice:
            selected = response.selected_choice.key.upper()
        answered = bool(selected)
        user_display = selected or _("No answer")
        status = "answered" if answered else "unanswered"
        result_label = _("Answered") if answered else _("No answer")
        if show_results:
            if not answered:
                status = "unanswered"
                result_label = _("No answer")
            elif selected in correct_choices:
                status = "correct"
                result_label = _("Correct")
            else:
                status = "incorrect"
                result_label = _("Incorrect")
        detail.update(
            {
                "status": status,
                "answered": answered,
                "user_display": user_display,
                "correct_display": correct_display,
                "result_label": result_label,
                "correct_choices": correct_choices,
                "selected_choice": selected,
            }
        )
        return detail

    def _feedback_true_false(self, question, response, show_results, detail):
        answers = {}
        if response and isinstance(response.true_false_answers, dict):
            answers = {str(k): bool(v) for k, v in response.true_false_answers.items()}

        statements = []
        statement_map = {}
        answered = False
        correct_segments = []
        user_segments = []
        for choice in question.choices.order_by("key"):
            key_id = str(choice.id)
            user_value = answers.get(key_id)
            if user_value is not None:
                answered = True
            key_label = choice.key.upper()
            user_label = (
                _("True")
                if user_value is True
                else _("False")
                if user_value is False
                else _("No answer")
            )
            correct_label = _("True") if choice.is_correct else _("False")
            status = "answered" if user_value is not None else "unanswered"
            result_label = _("Answered") if user_value is not None else _("No answer")
            if show_results:
                if user_value is None:
                    status = "unanswered"
                    result_label = _("No answer")
                elif bool(user_value) == bool(choice.is_correct):
                    status = "correct"
                    result_label = _("Correct")
                else:
                    status = "incorrect"
                    result_label = _("Incorrect")
            statements.append(
                {
                    "key": key_label,
                    "status": status,
                    "status_label": result_label,
                    "user_display": user_label,
                    "correct_display": correct_label,
                    "choice_id": choice.id,
                }
            )
            statement_map[choice.id] = statements[-1]
            correct_segments.append(f"{key_label}: {correct_label}")
            user_segments.append(f"{key_label}: {user_label}")

        if not answered:
            user_display = _("No answer")
        else:
            user_display = ", ".join(user_segments)
        correct_display = ", ".join(correct_segments)
        status = "answered" if answered else "unanswered"
        result_label = _("Answered") if answered else _("No answer")
        if show_results:
            if not answered:
                status = "unanswered"
                result_label = _("No answer")
            else:
                correct_count = sum(
                    1 for entry in statements if entry["status"] == "correct"
                )
                total = len(statements)
                if correct_count == total:
                    status = "correct"
                    result_label = _("Correct")
                elif correct_count == 0:
                    status = "incorrect"
                    result_label = _("Incorrect")
                else:
                    status = "partial"
                    result_label = _("Partially correct")

        detail.update(
            {
                "status": status,
                "answered": answered,
                "user_display": user_display,
                "correct_display": correct_display,
                "result_label": result_label,
                "statements": statements,
                "statement_map": statement_map,
            }
        )
        return detail

    def _feedback_short_answer(self, question, response, show_results, detail):
        expected = (question.short_answer or "").strip()
        user_text = ""
        if response:
            user_text = (response.short_answer_text or "").strip()
        answered = bool(user_text)
        status = "answered" if answered else "unanswered"
        result_label = _("Answered") if answered else _("No answer")
        if show_results:
            if not answered:
                status = "unanswered"
                result_label = _("No answer")
            else:
                expected_norm = ExamQuestion.normalize_short_answer(expected)
                given_norm = ExamQuestion.normalize_short_answer(user_text)
                if expected_norm and expected_norm == given_norm:
                    status = "correct"
                    result_label = _("Correct")
                else:
                    status = "incorrect"
                    result_label = _("Incorrect")
        detail.update(
            {
                "status": status,
                "answered": answered,
                "user_display": user_text or _("No answer"),
                "correct_display": expected or _("Not provided"),
                "result_label": result_label,
            }
        )
        return detail

    def _build_nav_tooltip(self, status_label, user_display, correct_display, show_results):
        parts = []
        if status_label:
            parts.append(_("Result: {status}").format(status=status_label))
        if user_display:
            parts.append(_("Your answer: {answer}").format(answer=user_display))
        if show_results and correct_display:
            parts.append(_("Correct answer: {answer}").format(answer=correct_display))
        return "\n".join(parts)

    @staticmethod
    def _get_part_key(part):
        if part == ExamQuestion.PART_MULTIPLE_CHOICE:
            return "part1"
        if part == ExamQuestion.PART_TRUE_FALSE:
            return "part2"
        if part == ExamQuestion.PART_SHORT_ANSWER:
            return "part3"
        return "part"


class ContestExamViolationView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        contest = get_object_or_404(Contest, key=kwargs["contest"])
        if contest.format_name != "thptqg":
            raise PermissionDenied

        profile = getattr(request, "profile", None)
        if profile is None:
            raise PermissionDenied

        try:
            participation = (
                ContestParticipation.objects.select_related("assigned_exam_paper")
                .filter(
                    contest=contest,
                    user=profile,
                    virtual__in=[
                        ContestParticipation.LIVE,
                        ContestParticipation.SPECTATE,
                    ],
                )
                .get()
            )
        except ContestParticipation.DoesNotExist:
            return JsonResponse({"error": "participation"}, status=400)

        if participation.exam_finalized_at:
            return JsonResponse(
                {"count": participation.exam_violation_count, "locked": True}
            )

        with transaction.atomic():
            participation = ContestParticipation.objects.select_for_update().get(
                pk=participation.pk
            )
            if participation.exam_locked:
                return JsonResponse(
                    {"count": participation.exam_violation_count, "locked": True}
                )
            participation.exam_violation_count += 1
            locked = participation.exam_violation_count >= 5
            update_fields = ["exam_violation_count"]
            if locked:
                participation.exam_locked = True
                participation.exam_locked_at = timezone.now()
                update_fields.extend(["exam_locked", "exam_locked_at"])
            participation.save(update_fields=update_fields)

        response = {
            "count": participation.exam_violation_count,
            "locked": participation.exam_locked,
            "limit": 5,
        }
        return JsonResponse(response)
