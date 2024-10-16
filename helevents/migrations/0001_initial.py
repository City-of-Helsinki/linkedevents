import django.contrib.auth.models
import django.core.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0006_require_contenttypes_0002"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.AutoField(
                        serialize=False,
                        verbose_name="ID",
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        null=True, verbose_name="last login", blank=True
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                        default=False,
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        help_text="Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        unique=True,
                        max_length=30,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[\\w.@+-]+$",
                                "Enter a valid username. This value may contain only letters, numbers and @/./+/-/_ characters.",
                                "invalid",
                            )
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        max_length=30, verbose_name="first name", blank=True
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        max_length=30, verbose_name="last name", blank=True
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        max_length=254, verbose_name="email address", blank=True
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                        default=False,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                        default=True,
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        verbose_name="date joined", default=django.utils.timezone.now
                    ),
                ),
                ("uuid", models.UUIDField(unique=True)),
                (
                    "department_name",
                    models.CharField(max_length=50, null=True, blank=True),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        blank=True,
                        related_name="user_set",
                        verbose_name="groups",
                        related_query_name="user",
                        to="auth.Group",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        help_text="Specific permissions for this user.",
                        blank=True,
                        related_name="user_set",
                        verbose_name="user permissions",
                        related_query_name="user",
                        to="auth.Permission",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
