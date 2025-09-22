from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.template.defaultfilters import floatformat
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext, gettext_lazy

from judge.contest_format.base import BaseContestFormat
from judge.contest_format.registry import register_contest_format
from judge.models.exam import ExamPaper, ExamQuestion, ExamResponse


@register_contest_format("thptqg")
class THPTQGContestFormat(BaseContestFormat):
    name = gettext_lazy("THPTQG Exam")

    @classmethod
    def validate(cls, config):
        if config is None:
            return
        if not isinstance(config, dict):
            raise ValidationError("thptqg contest expects a configuration dict")
        allowed_keys = {"subject"}
        unknown = set(config) - allowed_keys
        if unknown:
            raise ValidationError(
                "Invalid configuration keys for THPTQG contest: %s"
                % ", ".join(sorted(unknown))
            )
        subject = config.get("subject")
        if subject is not None and not isinstance(subject, str):
            raise ValidationError("subject must be a string if provided")

    def __init__(self, contest, config):
        super(THPTQGContestFormat, self).__init__(contest, config or {})

    def update_participation(self, participation):
        paper = self._get_paper_for_participation(participation)
        if not paper:
            participation.cumtime = 0
            participation.tiebreaker = 0
            participation.score = 0
            participation.format_data = {"_aggregate": {"score": 0}}
            participation.save()
            return

        questions = list(
            paper.questions.select_related("paper").prefetch_related("choices")
        )
        responses = {
            response.question_id: response
            for response in ExamResponse.objects.filter(
                participation=participation, question__paper=paper
            )
        }

        format_data = {}
        total_raw_points = 0.0
        total_max_points = 0.0
        total_correct_items = 0
        total_items = 0

        part_groups = {
            "part1": [],
            "part2": [],
            "part3": [],
        }
        for question in questions:
            if question.part == ExamQuestion.PART_MULTIPLE_CHOICE:
                part_groups["part1"].append(question)
            elif question.part == ExamQuestion.PART_TRUE_FALSE:
                part_groups["part2"].append(question)
            elif question.part == ExamQuestion.PART_SHORT_ANSWER:
                part_groups["part3"].append(question)

        for key, part_questions in part_groups.items():
            if not part_questions:
                continue
            entry = {
                "points": 0.0,
                "max_points": 0.0,
                "correct": 0,
                "total": 0,
                "questions": len(part_questions),
            }

            for question in part_questions:
                entry["max_points"] += float(question.max_points or 0.0)
                entry["total"] += question.total_items
                total_max_points += float(question.max_points or 0.0)
                total_items += question.total_items

                response = responses.get(question.id)
                if response:
                    entry["points"] += float(response.points)
                    entry["correct"] += response.correct_count
                    total_raw_points += float(response.points)
                    total_correct_items += response.correct_count
                else:
                    total_correct_items += 0

            format_data[key] = entry

        if total_max_points:
            scaled_score = total_raw_points / total_max_points * 10
        else:
            scaled_score = 0.0

        aggregate = {
            "raw_points": round(total_raw_points, 3),
            "max_points": round(total_max_points, 3),
            "correct_items": total_correct_items,
            "total_items": total_items,
            "score": scaled_score,
        }
        format_data["_aggregate"] = aggregate

        participation.cumtime = 0
        participation.tiebreaker = 0
        participation.score = round(scaled_score, self.contest.points_precision)
        participation.format_data = format_data
        participation.save()

    def display_user_problem(self, participation, contest_problem):
        key = getattr(contest_problem, "format_part_key", None)
        if key is None:
            return mark_safe('<td class="problem-score-col"></td>')

        data = (participation.format_data or {}).get(key)
        if not data:
            return mark_safe('<td class="problem-score-col"></td>')

        detail = format_html(
            '<div class="exam-points">{points}</div>'
            '<div class="exam-correct">{correct}/{total}</div>'
            '<div class="exam-questions">{answered}</div>',
            points=floatformat(data.get("points", 0), -self.contest.points_precision),
            correct=data.get("correct", 0),
            total=data.get("total", 0),
            answered=gettext("%(count)s questions")
            % {"count": data.get("questions", 0)},
        )
        return format_html(
            '<td class="problem-score-col exam-part">{detail}</td>',
            detail=detail,
        )

    def display_participation_result(self, participation):
        aggregate = (participation.format_data or {}).get("_aggregate", {})
        score = aggregate.get("score", participation.score)
        return format_html(
            '<td class="user-points exam-summary">'
            "<div class=\"exam-score\">{score}/10</div>"
            "<div class=\"exam-raw\">{raw}/{max_points}</div>"
            "<div class=\"exam-correct\">{correct}/{total}</div>"
            "</td>",
            score=floatformat(score, -self.contest.points_precision),
            raw=floatformat(aggregate.get("raw_points", 0), 2),
            max_points=floatformat(aggregate.get("max_points", 0), 2),
            correct=aggregate.get("correct_items", 0),
            total=aggregate.get("total_items", 0),
        )

    def get_problem_breakdown(self, participation, contest_problems):
        format_data = participation.format_data or {}
        return [
            format_data.get(getattr(contest_problem, "format_part_key", ""), {})
            for contest_problem in contest_problems
        ]

    def get_contest_problem_label_script(self):
        return """
            function(n)
                return tostring(math.floor(n + 1))
            end
        """

    def get_virtual_parts(self):
        paper = self.contest.exam_papers.order_by("id").first()
        if not paper:
            return []

        parts = []
        labels = {
            "part1": gettext("Part I"),
            "part2": gettext("Part II"),
            "part3": gettext("Part III"),
        }
        max_points = paper.max_points_by_part()
        for key in ("part1", "part2", "part3"):
            if key == "part3" and not paper.part3_questions:
                continue
            points = max_points.get(key, 0.0)
            label = labels.get(key, key.title())
            part = SimpleNamespace(
                format_part_key=key,
                label=label,
                points=points,
                problem=SimpleNamespace(name=label, code=key.upper()),
            )
            parts.append(part)
        return parts

    def _get_paper_for_participation(self, participation):
        paper = getattr(participation, "assigned_exam_paper", None)
        if paper and paper.contest_id == self.contest.id:
            return paper
        return self.contest.exam_papers.order_by("id").first()
