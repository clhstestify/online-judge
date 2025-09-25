from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import judge.models.choices
import judge.models.exam


class Migration(migrations.Migration):

    dependencies = [
        ("judge", "0141_exam_models"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="examquestion",
            options={
                "ordering": ["paper_id", "part", "number"],
                "verbose_name": "exam question",
                "verbose_name_plural": "exam questions",
            },
        ),
        migrations.AddField(
            model_name="examquestion",
            name="number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="contest",
            name="format_name",
            field=models.CharField(
                choices=[
                    ("atcoder", "AtCoder"),
                    ("default", "Default"),
                    ("ecoo", "ECOO"),
                    ("icpc", "ICPC"),
                    ("ioi", "IOI"),
                    ("ioi16", "New IOI"),
                    ("thptqg", "THPTQG Exam"),
                ],
                default="default",
                help_text="The contest format module to use.",
                max_length=32,
                verbose_name="contest format",
            ),
        ),
        migrations.AlterField(
            model_name="examquestion",
            name="contest_problem",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="exam_question",
                to="judge.contestproblem",
                verbose_name="contest problem",
            ),
        ),
        migrations.AlterField(
            model_name="examquestion",
            name="prompt",
            field=models.TextField(blank=True, verbose_name="question prompt"),
        ),
        migrations.AlterField(
            model_name="profile",
            name="timezone",
            field=models.CharField(
                choices=judge.models.choices.TIMEZONE,
                default=settings.DEFAULT_USER_TIME_ZONE,
                max_length=50,
                verbose_name="location",
            ),
        ),
        migrations.CreateModel(
            name="ExamPaper",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "subject",
                    models.CharField(
                        choices=[
                            ("math", "Mathematics"),
                            ("physics", "Physics"),
                            ("chemistry", "Chemistry"),
                            ("biology", "Biology"),
                            ("history", "History"),
                            ("geography", "Geography"),
                            ("civic_education", "Civic education"),
                            ("english", "English"),
                            ("foreign_language", "Other foreign language"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "part1_questions",
                    models.PositiveIntegerField(
                        default=40, verbose_name="part I questions"
                    ),
                ),
                (
                    "part2_questions",
                    models.PositiveIntegerField(
                        default=8, verbose_name="part II questions"
                    ),
                ),
                (
                    "part3_questions",
                    models.PositiveIntegerField(
                        default=6, verbose_name="part III questions"
                    ),
                ),
                (
                    "pdf",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=judge.models.exam.exam_pdf_upload_to,
                        verbose_name="exam PDF",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "contest",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_paper",
                        to="judge.contest",
                        verbose_name="contest",
                    ),
                ),
            ],
            options={
                "verbose_name": "exam paper",
                "verbose_name_plural": "exam papers",
            },
        ),
        migrations.AddField(
            model_name="examquestion",
            name="paper",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to="judge.exampaper",
                verbose_name="exam paper",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="examquestion",
            unique_together={("paper", "part", "number")},
        ),
    ]
