from django.db import migrations


def delete_existing_knox_tokens(apps, schema_editor):
    token_model = apps.get_model("knox", "Authtoken")
    token_model.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("data_analytics", "0002_new_token_model"),
        ("knox", "__latest__"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS data_analytics_dataanalyticsauthtoken",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(delete_existing_knox_tokens, migrations.RunPython.noop),
    ]
