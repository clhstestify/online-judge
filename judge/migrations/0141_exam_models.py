# Generated manually for exam models
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ("judge", "0140_alter_contest_format_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamQuestion",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("part", models.CharField(choices=[
                    ("multiple_choice", "Multiple choice"),
                    ("true_false", "True/False"),
                    ("short_answer", "Short answer"),
                ], max_length=32)),
                ("prompt", models.TextField(verbose_name="question prompt")),
                ("max_points", models.FloatField(default=0.25)),
                (
                    "short_answer",
                    models.CharField(
                        blank=True,
                        help_text="Expected answer for short-answer questions.",
                        max_length=64,
                        verbose_name="short answer",
                    ),
                ),
                (
                    "contest_problem",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_question",
                        to="judge.contestproblem",
                        verbose_name="contest problem",
                    ),
                ),
            ],
            options={
                "verbose_name": "exam question",
                "verbose_name_plural": "exam questions",
            },
        ),
        migrations.CreateModel(
            name="ExamChoice",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=16, verbose_name="label")),
                ("text", models.TextField(blank=True, verbose_name="text")),
                ("is_correct", models.BooleanField(default=False, verbose_name="is correct")),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="judge.examquestion",
                        verbose_name="question",
                    ),
                ),
            ],
            options={
                "ordering": ["key"],
                "verbose_name": "exam choice",
                "verbose_name_plural": "exam choices",
            },
        ),
        migrations.CreateModel(
            name="ExamResponse",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("true_false_answers", jsonfield.fields.JSONField(blank=True, null=True)),
                ("short_answer_text", models.CharField(blank=True, max_length=64)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("points", models.FloatField(default=0)),
                ("correct_count", models.PositiveIntegerField(default=0)),
                ("total_count", models.PositiveIntegerField(default=0)),
                (
                    "participation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_responses",
                        to="judge.contestparticipation",
                        verbose_name="participation",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="judge.examquestion",
                        verbose_name="question",
                    ),
                ),
                (
                    "selected_choice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="responses",
                        to="judge.examchoice",
                        verbose_name="selected choice",
                    ),
                ),
            ],
            options={
                "verbose_name": "exam response",
                "verbose_name_plural": "exam responses",
            },
        ),
        migrations.AlterUniqueTogether(
            name="examresponse",
            unique_together={("question", "participation")},
        ),
    ]
