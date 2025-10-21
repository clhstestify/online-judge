import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from judge.models import (
    Contest,
    ContestParticipation,
    ContestSubmission,
    Language,
    Submission,
)


def _duration_to_hms(delta):
    if delta is None:
        return "0:00:00.000"
    total_ms = int(round(max(delta.total_seconds(), 0) * 1000))
    hours, remainder = divmod(total_ms // 1000, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = total_ms % 1000
    return f"{hours}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _duration_to_iso(delta):
    if delta is None:
        return "PT0S"
    total_seconds = max(delta.total_seconds(), 0)
    seconds = int(total_seconds)
    milliseconds = int(round((total_seconds - seconds) * 1000))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = ["PT"]
    if hours:
        parts.append(f"{hours}H")
    if minutes:
        parts.append(f"{minutes}M")
    if seconds or milliseconds or not (hours or minutes):
        if milliseconds:
            parts.append(f"{seconds}.{milliseconds:03d}S")
        else:
            parts.append(f"{seconds}S")
    return "".join(parts)


def _contest_queryset(user):
    qs = Contest.get_visible_contests(user).filter(format_name="icpc")
    return [contest for contest in qs if contest.can_see_full_scoreboard(user)]


def _check_contest_access(request, contest):
    if not request.user.is_authenticated:
        raise PermissionDenied()
    if contest.format_name != "icpc":
        raise PermissionDenied()
    if not contest.can_see_full_scoreboard(request.user):
        raise PermissionDenied()


def _contest_data(contest):
    duration = contest.end_time - contest.start_time
    freeze_duration = None
    if contest.freeze_after:
        freeze_start = contest.start_time + contest.freeze_after
        if contest.end_time > freeze_start:
            freeze_duration = contest.end_time - freeze_start
        else:
            freeze_duration = None

    config = getattr(contest.format, "config", {})
    penalty = config.get("penalty")

    return {
        "id": contest.key,
        "name": contest.name,
        "formal_name": contest.name,
        "start_time": contest.start_time.isoformat(),
        "duration": _duration_to_hms(duration),
        "scoreboard_freeze_duration": _duration_to_hms(freeze_duration),
        "penalty_time": penalty,
        "penalty_type": "time" if penalty else None,
        "scoreboard_type": "pass-fail",
    }


def _problem_label(contest, index):
    try:
        return contest.get_label_for_problem(index)
    except Exception:
        # Fallback to alphabetical labels if custom script fails.
        label = ""
        n = index + 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            label = chr(ord("A") + remainder) + label
        return label or str(index + 1)


@login_required
def contest_list(request):
    contests = [_contest_data(contest) for contest in _contest_queryset(request.user)]
    return JsonResponse(contests, safe=False)


@login_required
def contest_detail(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    return JsonResponse(_contest_data(contest))


def _contest_problem_queryset(contest):
    return (
        contest.contest_problems.select_related("problem")
        .prefetch_related("problem__allowed_languages")
        .order_by("order", "id")
    )


def _contest_problems(contest):
    problems = list(_contest_problem_queryset(contest))
    result = []
    for index, contest_problem in enumerate(problems):
        problem = contest_problem.problem
        result.append(
            {
                "id": problem.code,
                "label": _problem_label(contest, index),
                "name": problem.name,
                "ordinal": index,
                "time_limit": problem.time_limit,
                "points": contest_problem.points,
            }
        )
    return result


def _contest_languages(contest, problems=None):
    if problems is None:
        problems = list(_contest_problem_queryset(contest))

    languages = []
    language_ids = set()
    requires_all_languages = False

    for contest_problem in problems:
        allowed_languages = list(contest_problem.problem.allowed_languages.all())
        if not allowed_languages:
            requires_all_languages = True
            break
        for language in allowed_languages:
            if language.id not in language_ids:
                language_ids.add(language.id)
                languages.append(language)

    if requires_all_languages or not languages:
        return list(Language.objects.order_by("key"))

    languages.sort(key=lambda language: language.key)
    return languages


@login_required
def contest_problem_list(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    return JsonResponse(_contest_problems(contest), safe=False)


def _contest_participations(contest):
    return (
        contest.users.filter(
            virtual=ContestParticipation.LIVE,
            is_disqualified=False,
        )
        .select_related("user__user")
        .prefetch_related("user__organizations")
        .order_by("-score", "cumtime", "user__user__username")
    )


def _organizations_from_participations(participations):
    organizations = {}
    for participation in participations:
        profile = participation.user
        for organization in profile.organizations.all():
            organizations[organization.id] = organization
    return organizations


@login_required
def contest_organization_list(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    participations = _contest_participations(contest)
    organizations = _organizations_from_participations(participations)
    data = [
        {
            "id": str(org.id),
            "name": org.short_name or org.name,
            "formal_name": org.name,
        }
        for org in organizations.values()
    ]
    return JsonResponse(data, safe=False)


def _resolve_organization_id(profile, organizations):
    for organization in profile.organizations.all():
        if organization.id in organizations:
            return str(organization.id)
    return None


@login_required
def contest_team_list(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    participations = list(_contest_participations(contest))
    organizations = _organizations_from_participations(participations)
    teams = []
    for participation in participations:
        profile = participation.user
        user = profile.user
        name = user.get_full_name() or user.username
        teams.append(
            {
                "id": str(participation.id),
                "name": name,
                "display_name": name,
                "organization_id": _resolve_organization_id(
                    profile, organizations
                ),
                "members": [
                    {
                        "id": str(user.id),
                        "name": name,
                    }
                ],
            }
        )
    return JsonResponse(teams, safe=False)


@login_required
def contest_language_list(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    languages = _contest_languages(contest)
    data = [
        {
            "id": language.key,
            "name": language.name,
            "extensions": [language.extension],
        }
        for language in languages
    ]
    return JsonResponse(data, safe=False)


def _judgement_types():
    penalty_codes = {"WA", "TLE", "MLE", "OLE", "IR", "RTE"}
    results = []
    for code, name in Submission.RESULT:
        results.append(
            {
                "id": code,
                "name": str(name),
                "penalty": code in penalty_codes,
                "solved": code == "AC",
            }
        )
    return results


@login_required
def contest_judgement_type_list(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    return JsonResponse(_judgement_types(), safe=False)


def _first_solves(contest, problems):
    mapping = {}
    for contest_problem in problems:
        submission = (
            ContestSubmission.objects.filter(
                problem=contest_problem,
                participation__contest=contest,
                participation__virtual=ContestParticipation.LIVE,
                participation__is_disqualified=False,
                submission__result="AC",
                points__gte=contest_problem.points,
            )
            .select_related("submission")
            .order_by("submission__date")
            .first()
        )
        if submission:
            mapping[contest_problem.problem.code] = submission.participation_id
    return mapping


@login_required
def contest_scoreboard(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    problems = list(_contest_problem_queryset(contest))
    participations = list(_contest_participations(contest))
    first_solves = _first_solves(contest, problems)

    rows = []
    for rank, participation in enumerate(participations, start=1):
        format_data = participation.format_data or {}
        problem_results = []
        solved_count = 0
        for contest_problem in problems:
            problem_key = str(contest_problem.id)
            result_data = format_data.get(problem_key, {})
            solved = result_data.get("points", 0) >= contest_problem.points
            penalty = int(result_data.get("penalty", 0) or 0)
            num_judged = penalty + (1 if solved else 0)
            entry = {
                "problem_id": contest_problem.problem.code,
                "num_judged": num_judged,
                "num_pending": 0,
                "incorrect": penalty,
                "solved": solved,
                "is_first_to_solve": participation.id
                == first_solves.get(contest_problem.problem.code),
            }
            if solved:
                solved_count += 1
                entry["time"] = _duration_to_iso(
                    timedelta(seconds=result_data.get("time", 0))
                )
            problem_results.append(entry)

        rows.append(
            {
                "rank": rank,
                "team_id": str(participation.id),
                "score": {
                    "num_solved": solved_count,
                    "total_time": int(participation.cumtime),
                },
                "problems": problem_results,
            }
        )

    now = timezone.now()
    freeze_time = (
        contest.start_time + contest.freeze_after if contest.freeze_after else None
    )
    contest_time = None
    if now >= contest.start_time:
        contest_time = min(now, contest.end_time) - contest.start_time

    data = {
        "time": now.isoformat(),
        "contest_time": _duration_to_iso(contest_time),
        "state": {
            "started": now >= contest.start_time,
            "ended": now >= contest.end_time,
            "frozen": bool(freeze_time and now >= freeze_time),
            "finalized": now >= contest.end_time,
            "thawed": now >= contest.end_time,
        },
        "rows": rows,
    }
    return JsonResponse(data)


def _format_contest_time(contest, timestamp):
    if timestamp is None:
        return None
    return _duration_to_hms(timestamp - contest.start_time)


def _event_feed_static_events(contest, participations, problems):
    events = []

    def add_event(event_type, entity_id, data):
        events.append(
            {
                "type": event_type,
                "id": f"{event_type}-{entity_id}",
                "op": "create",
                "data": data,
            }
        )

    add_event("contests", contest.key, _contest_data(contest))

    organizations = _organizations_from_participations(participations)
    for organization in organizations.values():
        add_event(
            "organizations",
            organization.id,
            {
                "id": str(organization.id),
                "name": organization.short_name or organization.name,
                "formal_name": organization.name,
            },
        )

    for participation in participations:
        profile = participation.user
        user = profile.user
        name = user.get_full_name() or user.username
        add_event(
            "teams",
            participation.id,
            {
                "id": str(participation.id),
                "name": name,
                "display_name": name,
                "organization_id": _resolve_organization_id(
                    profile, organizations
                ),
            },
        )

    for judgement in _judgement_types():
        add_event("judgement-types", judgement["id"], judgement)

    for language in _contest_languages(contest, problems):
        add_event(
            "languages",
            language.key,
            {
                "id": language.key,
                "name": language.name,
            },
        )

    for index, contest_problem in enumerate(problems):
        problem = contest_problem.problem
        add_event(
            "problems",
            problem.code,
            {
                "id": problem.code,
                "label": _problem_label(contest, index),
                "name": problem.name,
                "ordinal": index,
                "time_limit": problem.time_limit,
            },
        )

    return events


def _contest_submissions(contest):
    return (
        ContestSubmission.objects.filter(
            participation__contest=contest,
            participation__virtual=ContestParticipation.LIVE,
            participation__is_disqualified=False,
        )
        .select_related("submission", "participation", "problem__problem")
        .order_by("submission__date", "submission__id")
    )


@login_required
def contest_event_feed(request, contest_id):
    contest = get_object_or_404(Contest, key=contest_id)
    _check_contest_access(request, contest)
    problems = list(_contest_problem_queryset(contest))
    participations = list(_contest_participations(contest))

    events = _event_feed_static_events(contest, participations, problems)

    judgement_counter = 0
    for contest_submission in _contest_submissions(contest):
        submission = contest_submission.submission
        if submission is None:
            continue
        participation = contest_submission.participation
        if participation is None:
            continue

        submission_id = str(submission.id)
        language_id = submission.language.key if submission.language else None
        contest_time = _format_contest_time(contest, submission.date)

        submission_data = {
            "id": submission_id,
            "problem_id": contest_submission.problem.problem.code,
            "team_id": str(participation.id),
            "language_id": language_id,
            "files": [],
            "contest_time": contest_time,
            "time": submission.date.isoformat(),
        }
        events.append(
            {
                "type": "submissions",
                "id": f"submission-{submission_id}",
                "op": "create",
                "data": submission_data,
            }
        )

        if submission.result:
            judgement_counter += 1
            judged_time = submission.judged_date or submission.date
            judgement_data = {
                "id": str(submission.id),
                "submission_id": submission_id,
                "judgement_type_id": submission.result,
                "max_run_time": submission.time,
                "start_time": submission.date.isoformat(),
                "start_contest_time": contest_time,
                "end_time": judged_time.isoformat(),
                "end_contest_time": _format_contest_time(contest, judged_time),
            }
            events.append(
                {
                    "type": "judgements",
                    "id": f"judgement-{judgement_counter}",
                    "op": "create",
                    "data": judgement_data,
                }
            )

    content = "\n".join(json.dumps(event, sort_keys=True) for event in events)
    return HttpResponse(content, content_type="application/x-ndjson")

