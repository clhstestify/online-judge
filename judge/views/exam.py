from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from judge.forms import ExamAnswerForm
from judge.models import ContestParticipation
from judge.models.exam import ExamQuestion, ExamResponse
from judge.utils.views import generic_message
from judge.views.contests import ContestMixin


class ExamTakeView(LoginRequiredMixin, ContestMixin, View):
    template_name = "exam/take.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.format_name != "thptqg":
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_participation(self):
        try:
            return ContestParticipation.objects.get(
                contest=self.object,
                user=self.request.profile,
                virtual=ContestParticipation.LIVE,
            )
        except ContestParticipation.DoesNotExist:
            return None

    def get_questions(self):
        return list(
            ExamQuestion.objects.filter(
                contest_problem__contest=self.object
            )
            .select_related(
                "contest_problem",
                "contest_problem__problem",
            )
            .prefetch_related("choices")
            .order_by("contest_problem__order", "id")
        )

    def get_current_question(self, request, questions):
        selected = request.GET.get("question") or request.POST.get("question")
        if selected:
            try:
                question_id = int(selected)
            except (TypeError, ValueError):
                question_id = None
            else:
                for question in questions:
                    if question.id == question_id:
                        return question
        return questions[0] if questions else None

    def get_question_index(self, question, questions):
        for idx, item in enumerate(questions):
            if item.id == question.id:
                return idx
        return 0

    def question_url(self, question=None):
        url = reverse("contest_exam_take", args=[self.object.key])
        if question is not None:
            return f"{url}?question={question.id}"
        return url

    def get_navigation(self, questions, responses):
        progress = []
        contest = self.object
        for idx, question in enumerate(questions):
            response = responses.get(question.id)
            progress.append(
                {
                    "id": question.id,
                    "index": idx + 1,
                    "label": contest.get_label_for_problem(idx),
                    "answered": response is not None,
                    "choice": response.selected_choice if response else None,
                    "url": self.question_url(question),
                }
            )
        return progress

    def render_no_participation(self, request):
        return generic_message(
            request,
            _("Not participating"),
            _("You must join the contest before taking the exam."),
        )

    def get(self, request, *args, **kwargs):
        participation = self.get_participation()
        if participation is None:
            return self.render_no_participation(request)

        questions = self.get_questions()
        if not questions:
            return generic_message(
                request,
                _("No questions available"),
                _("This contest does not have any exam questions configured."),
            )

        question = self.get_current_question(request, questions)
        question_ids = [q.id for q in questions]
        responses = {
            response.question_id: response
            for response in ExamResponse.objects.filter(
                participation=participation,
                question_id__in=question_ids,
            )
        }
        response = responses.get(question.id)

        form = ExamAnswerForm(
            question=question,
            initial={"choice": response.selected_choice} if response else None,
        )

        context = self.build_context(
            participation, questions, question, form, responses, read_only=participation.ended
        )
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        participation = self.get_participation()
        if participation is None:
            return self.render_no_participation(request)

        questions = self.get_questions()
        if not questions:
            return generic_message(
                request,
                _("No questions available"),
                _("This contest does not have any exam questions configured."),
            )

        question = self.get_current_question(request, questions)
        question_ids = [q.id for q in questions]
        responses = {
            response.question_id: response
            for response in ExamResponse.objects.filter(
                participation=participation,
                question_id__in=question_ids,
            )
        }

        form = ExamAnswerForm(request.POST, question=question)
        if participation.ended:
            form.add_error(None, _("Your contest participation has ended."))
        elif form.is_valid():
            choice = form.cleaned_data["choice"]
            ExamResponse.record_answer(participation, question, choice)
            participation.recompute_results()
            nav = request.POST.get("nav")
            if nav == "prev":
                target = self.get_previous_question(question, questions)
            elif nav == "next":
                target = self.get_next_question(question, questions)
            else:
                target = question
            return redirect(self.question_url(target))

        context = self.build_context(
            participation, questions, question, form, responses, read_only=participation.ended
        )
        return render(request, self.template_name, context)

    def get_previous_question(self, question, questions):
        idx = self.get_question_index(question, questions)
        if idx > 0:
            return questions[idx - 1]
        return question

    def get_next_question(self, question, questions):
        idx = self.get_question_index(question, questions)
        if idx + 1 < len(questions):
            return questions[idx + 1]
        return question

    def build_context(
        self,
        participation,
        questions,
        question,
        form,
        responses,
        read_only=False,
    ):
        idx = self.get_question_index(question, questions)
        progress = self.get_navigation(questions, responses)
        response = responses.get(question.id)
        if read_only:
            form.fields["choice"].disabled = True
        return {
            "contest": self.object,
            "participation": participation,
            "question": question,
            "question_index": idx + 1,
            "total_questions": len(questions),
            "form": form,
            "progress": progress,
            "current_response": response,
            "read_only": read_only,
            "previous_question": self.get_previous_question(question, questions),
            "next_question": self.get_next_question(question, questions),
            "question_url": self.question_url,
            "end_time": participation.end_time,
        }
