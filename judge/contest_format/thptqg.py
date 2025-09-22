from django.core.exceptions import ValidationError
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from judge.contest_format.base import BaseContestFormat
from judge.contest_format.registry import register_contest_format


@register_contest_format("thptqg")
class THPTQGContestFormat(BaseContestFormat):
    name = gettext_lazy("Multiple Choice Exam")

    @classmethod
    def validate(cls, config):
        if config not in (None, {}):
            raise ValidationError("thptqg contest expects no configuration")

    def update_participation(self, participation):
        format_data = {}
        total_points = 0

        responses = participation.exam_responses.select_related(
            "question__contest_problem"
        )

        for response in responses:
            contest_problem = response.question.contest_problem
            total_points += response.points
            delta = None
            if response.updated_at:
                delta = (response.updated_at - participation.start).total_seconds()
                if delta < 0:
                    delta = 0

            format_data[str(contest_problem.id)] = {
                "points": response.points,
                "choice": response.selected_choice,
                "correct_choice": response.question.correct_choice,
                "time": delta,
            }

        self.handle_frozen_state(participation, format_data)
        participation.cumtime = 0
        participation.score = round(total_points, self.contest.points_precision)
        participation.tiebreaker = 0
        participation.format_data = format_data
        participation.save(
            update_fields=["cumtime", "score", "tiebreaker", "format_data"]
        )

    def display_user_problem(self, participation, contest_problem):
        format_data = (participation.format_data or {}).get(
            str(contest_problem.id)
        )
        if not format_data:
            return mark_safe('<td class="problem-score-col"></td>')

        state = self.best_solution_state(
            format_data["points"], contest_problem.points
        )
        return format_html(
            '<td class="problem-score-col {state}"><span class="exam-choice">{choice}</span><div class="solving-time">{points}</div></td>',
            state=state,
            choice=format_data.get("choice", ""),
            points=floatformat(
                format_data["points"], -self.contest.points_precision
            ),
        )

    def display_participation_result(self, participation):
        return format_html(
            '<td class="user-points">{points}</td>',
            points=floatformat(participation.score, -self.contest.points_precision),
        )

    def get_problem_breakdown(self, participation, contest_problems):
        return [
            (participation.format_data or {}).get(str(contest_problem.id))
            for contest_problem in contest_problems
        ]

    def user_submissions_url(self, participation, contest_problem):
        return reverse(
            "contest_user_submissions_ajax",
            args=[
                self.contest.key,
                participation.id,
                contest_problem.problem.code,
            ],
        )

    def get_contest_problem_label_script(self):
        return """
            function(n)
                return tostring(math.floor(n + 1))
            end
        """
