from __future__ import annotations

import math
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from judge.contest_format.base import BaseContestFormat
from judge.contest_format.registry import register_contest_format
from judge.utils.timedelta import nice_repr


def _should_count_wrong(result: str | None) -> bool:
    if result is None:
        return False
    return result not in {"CE", "IE"}


@register_contest_format("codeforces")
class CodeforcesContestFormat(BaseContestFormat):
    name = gettext_lazy("QTOJ Codeforces")

    @classmethod
    def validate(cls, config):
        if config is not None and (not isinstance(config, dict) or config):
            raise ValidationError(
                "Codeforces contest expects no config or empty dict as config"
            )

    def __init__(self, contest, config):
        super(CodeforcesContestFormat, self).__init__(contest, config)

    def update_participation(self, participation):
        contest_problems = {
            problem.id: problem for problem in self.contest.contest_problems.all()
        }

        freeze_cutoff = None
        if self.contest.freeze_after:
            freeze_cutoff = participation.start + self.contest.freeze_after

        submissions = participation.submissions.select_related("submission", "problem")
        if freeze_cutoff is not None:
            submissions = submissions.filter(submission__date__lt=freeze_cutoff)
        submissions = submissions.order_by("submission__date")

        stats = {
            problem_id: {
                "wrong": 0,
                "solved": False,
                "score": 0.0,
                "time_seconds": None,
            }
            for problem_id in contest_problems
        }

        for contest_submission in submissions:
            problem_id = contest_submission.problem_id
            problem = contest_problems[problem_id]
            data = stats[problem_id]

            if data["solved"]:
                continue

            submission = contest_submission.submission
            submission_result = submission.result
            full_score = submission_result == "AC" and (
                contest_submission.points is None
                or contest_submission.points >= problem.points
            )

            if full_score:
                solve_time = (submission.date - participation.start).total_seconds()
                minutes = int(solve_time // 60)
                base_points = float(problem.points)
                dynamic_score = base_points - (base_points * minutes / 250.0) - (
                    50 * data["wrong"]
                )
                score = max(0.3 * base_points, dynamic_score)
                score = max(score, 0.0)

                data.update(
                    {
                        "solved": True,
                        "score": score,
                        "time_seconds": solve_time,
                    }
                )
            else:
                if _should_count_wrong(submission_result):
                    data["wrong"] += 1

        total_score = 0.0
        total_penalty_minutes = 0
        last_solve_time = 0.0
        format_data = {}

        for problem_id, data in stats.items():
            problem = contest_problems[problem_id]
            solved = data["solved"]
            wrong = data["wrong"]
            score = data["score"] if solved else 0.0
            time_seconds = data["time_seconds"] if solved else None

            if solved:
                total_score += score
                minutes = int(time_seconds // 60)
                total_penalty_minutes += minutes + 20 * wrong
                last_solve_time = max(last_solve_time, time_seconds)

            format_data[str(problem_id)] = {
                "points": problem.points if solved else 0,
                "score": score,
                "time": time_seconds,
                "wrong": wrong,
                "solved": solved,
            }

        self.handle_frozen_state(participation, format_data)

        for value in format_data.values():
            value.setdefault("score", 0.0)
            value.setdefault("time", None)

        participation.cumtime = max(0, int(math.ceil(total_penalty_minutes * 60)))
        participation.score = round(total_score, self.contest.points_precision)
        participation.tiebreaker = last_solve_time
        participation.format_data = format_data
        participation.save()

    def display_user_problem(self, participation, contest_problem):
        format_data = (participation.format_data or {}).get(str(contest_problem.id))
        if not format_data:
            return mark_safe('<td class="problem-score-col"></td>')

        solved = format_data.get("solved")
        wrong = format_data.get("wrong", 0)
        frozen = " frozen" if format_data.get("frozen") else ""
        url = reverse(
            "contest_user_submissions_ajax",
            args=[
                self.contest.key,
                participation.id,
                contest_problem.problem.code,
            ],
        )

        if solved:
            score = format_data.get("score", 0.0)
            time_seconds = format_data.get("time") or 0.0
            wrong_info = (
                format_html(
                    '<small class="wrong-attempts">(-{wrong})</small>', wrong=wrong
                )
                if wrong
                else ""
            )

            return format_html(
                '<td class="{state} problem-score-col"><a data-featherlight="{url}" '
                'href="#">{points}{wrong_info}<div class="solving-time">{time}</div></a></td>',
                state=(
                    (
                        "pretest-"
                        if self.contest.run_pretests_only
                        and contest_problem.is_pretested
                        else ""
                    )
                    + "full-score"
                    + frozen
                ),
                url=url,
                points=floatformat(score, -self.contest.points_precision),
                wrong_info=wrong_info,
                time=nice_repr(timedelta(seconds=time_seconds), "noday"),
            )

        if wrong:
            return format_html(
                '<td class="{state} problem-score-col"><a data-featherlight="{url}" '
                'href="#">-{wrong}</a></td>',
                state=(
                    (
                        "pretest-"
                        if self.contest.run_pretests_only
                        and contest_problem.is_pretested
                        else ""
                    )
                    + "failed-score"
                    + frozen
                ),
                url=url,
                wrong=wrong,
            )

        return mark_safe('<td class="problem-score-col"></td>')

    def display_participation_result(self, participation):
        return format_html(
            '<td class="user-points">{points}<div class="solving-time">{penalty}</div></td>',
            points=floatformat(participation.score, -self.contest.points_precision),
            penalty=nice_repr(timedelta(seconds=participation.cumtime), "noday"),
        )

    def get_problem_breakdown(self, participation, contest_problems):
        return [
            (participation.format_data or {}).get(str(contest_problem.id))
            for contest_problem in contest_problems
        ]

    def get_contest_problem_label_script(self):
        return """
            function(n)
                return tostring(math.floor(n + 1))
            end
        """
