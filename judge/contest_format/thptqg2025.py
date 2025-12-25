from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext, gettext_lazy

from judge.contest_format.base import BaseContestFormat
from judge.contest_format.registry import register_contest_format
from judge.utils.timedelta import nice_repr


@register_contest_format("thptqg-2025")
class THPTQG2025ContestFormat(BaseContestFormat):
    name = gettext_lazy("THPTQG 2025 Multiple Choice")

    _ALLOWED_CONFIG_KEYS = {"max_score", "use_time_penalty"}
    _DEFAULT_MAX_SCORE = 10.0

    def __init__(self, contest, config):
        super().__init__(contest, config)
        config = config or {}
        self.max_score = float(config.get("max_score", self._DEFAULT_MAX_SCORE))
        self.use_time_penalty = config.get("use_time_penalty", False)
        self._problem_points_cache = None
        self._total_points_cache = None

    @classmethod
    def validate(cls, config):
        if config is None:
            return
        if not isinstance(config, dict):
            raise ValidationError(
                "thptqg-2025 contest expects a dictionary as configuration"
            )
        unknown_keys = set(config) - cls._ALLOWED_CONFIG_KEYS
        if unknown_keys:
            raise ValidationError(
                "Unsupported configuration keys for thptqg-2025 contest: %s"
                % ", ".join(sorted(unknown_keys))
            )
        if "max_score" in config:
            max_score = config["max_score"]
            if not isinstance(max_score, (int, float)):
                raise ValidationError("max_score must be a number")
            if max_score <= 0:
                raise ValidationError("max_score must be positive")
        if "use_time_penalty" in config and not isinstance(
            config["use_time_penalty"], bool
        ):
            raise ValidationError("use_time_penalty must be a boolean")

    def _problem_points(self):
        if self._problem_points_cache is None:
            self._problem_points_cache = dict(
                self.contest.contest_problems.values_list("id", "points")
            )
        return self._problem_points_cache

    def _total_points(self):
        if self._total_points_cache is None:
            self._total_points_cache = sum(self._problem_points().values())
        return self._total_points_cache

    def _normalized_weight(self, contest_problem_id):
        total = self._total_points()
        problem_points = self._problem_points().get(contest_problem_id, 0)
        if total and problem_points:
            return self.max_score * problem_points / total
        return 0.0

    def _normalized_score(self, earned_points, contest_problem_id):
        problem_points = self._problem_points().get(contest_problem_id, 0)
        if not problem_points:
            return 0.0
        return earned_points / problem_points * self._normalized_weight(
            contest_problem_id
        )

    def update_participation(self, participation):
        self._problem_points_cache = None
        self._total_points_cache = None
        cumtime = 0
        raw_points_total = 0.0
        normalized_total = 0.0
        format_data = {}

        queryset = participation.submissions

        if self.contest.freeze_after:
            queryset = queryset.filter(
                submission__date__lt=participation.start + self.contest.freeze_after
            )

        queryset = queryset.values("problem_id").annotate(
            time=Max("submission__date"),
            points=Max("points"),
        )

        for result in queryset:
            submission_time = result["time"]
            if submission_time is None:
                continue
            dt = (submission_time - participation.start).total_seconds()
            earned_points = result["points"] or 0.0
            contest_problem_id = result["problem_id"]
            normalized_points = self._normalized_score(
                earned_points, contest_problem_id
            )
            format_data[str(contest_problem_id)] = {
                "time": dt,
                "points": earned_points,
                "normalized": normalized_points,
            }
            raw_points_total += earned_points
            normalized_total += normalized_points
            if self.use_time_penalty and earned_points:
                cumtime += dt

        self.handle_frozen_state(participation, format_data)

        format_data["_meta"] = {
            "raw_total": raw_points_total,
            "max_total": self._total_points(),
            "normalized_total": normalized_total,
        }

        normalized_total = max(0.0, min(normalized_total, self.max_score))
        format_data["_meta"]["normalized_total"] = normalized_total
        participation.cumtime = max(cumtime, 0)
        participation.score = round(normalized_total, self.contest.points_precision)
        participation.tiebreaker = -normalized_total
        participation.format_data = format_data
        participation.save()

    def display_user_problem(self, participation, contest_problem):
        format_data = (participation.format_data or {}).get(str(contest_problem.id))
        if format_data:
            normalized_points = format_data.get("normalized") or 0
            normalized_display = (
                format_html(
                    '<div class="thptqg-normalized">+{}</div>',
                    floatformat(
                        normalized_points, -self.contest.points_precision
                    ),
                )
                if normalized_points
                else ""
            )
            return format_html(
                '<td class="{state} problem-score-col"><a data-featherlight="{url}" href="#">'
                "{earned}/{total}{normalized}<div class=\"solving-time\">{time}</div></a></td>",
                state=(
                    (
                        "pretest-"
                        if self.contest.run_pretests_only
                        and contest_problem.is_pretested
                        else ""
                    )
                    + self.best_solution_state(
                        format_data["points"], contest_problem.points
                    )
                    + (" frozen" if format_data.get("frozen") else "")
                ),
                url=reverse(
                    "contest_user_submissions_ajax",
                    args=[
                        self.contest.key,
                        participation.id,
                        contest_problem.problem.code,
                    ],
                ),
                earned=floatformat(
                    format_data["points"], -self.contest.points_precision
                ),
                total=floatformat(
                    self._problem_points().get(contest_problem.id, 0),
                    -self.contest.points_precision,
                ),
                normalized=mark_safe(normalized_display),
                time=nice_repr(
                    timedelta(seconds=format_data.get("time", 0)), "noday"
                ),
            )
        return mark_safe('<td class="problem-score-col"></td>')

    def display_participation_result(self, participation):
        format_data = participation.format_data or {}
        meta = format_data.get("_meta", {})
        raw_total = meta.get("raw_total")
        if raw_total is None:
            raw_total = sum(
                (format_data.get(str(cp_id), {}).get("points") or 0)
                for cp_id in self._problem_points()
            )
        max_total = meta.get("max_total") or self._total_points()
        raw_summary = (
            gettext("%(earned)s/%(total)s correct")
            % {
                "earned": floatformat(raw_total, -self.contest.points_precision),
                "total": floatformat(max_total, -self.contest.points_precision),
            }
            if max_total
            else gettext("%(earned)s correct")
            % {
                "earned": floatformat(raw_total, -self.contest.points_precision)
            }
        )
        cumtime_display = (
            nice_repr(timedelta(seconds=participation.cumtime), "noday")
            if self.use_time_penalty and participation.cumtime
            else (nice_repr(timedelta(seconds=0), "noday") if self.use_time_penalty else "—")
        )
        return format_html(
            '<td class="user-points">{points}<div class="thptqg-raw-summary">{raw}</div><div class="solving-time">{cumtime}</div></td>',
            points=floatformat(participation.score, -self.contest.points_precision),
            raw=raw_summary,
            cumtime=cumtime_display,
        )

    def get_problem_breakdown(self, participation, contest_problems):
        data = participation.format_data or {}
        breakdown = []
        for contest_problem in contest_problems:
            entry = data.get(str(contest_problem.id))
            if entry:
                entry = entry.copy()
                entry.setdefault(
                    "normalized",
                    self._normalized_score(entry.get("points", 0), contest_problem.id),
                )
                entry.setdefault("weight", self._normalized_weight(contest_problem.id))
            breakdown.append(entry)
        return breakdown

    def get_contest_problem_label_script(self):
        return """
            function(n)
                return "Câu " .. tostring(math.floor(n + 1))
            end
        """
