# Generated by Django 1.9.13 on 2017-07-11 15:35

import mptt
from django.db import migrations


def forward(apps, schema_editor):
    # the zero mptt fields won't do, we need a treemanager to build the mptt tree
    manager = mptt.managers.TreeManager()
    Organization = apps.get_model("events", "Organization")
    manager.model = Organization
    mptt.register(Organization)
    manager.contribute_to_class(Organization, "objects")
    manager.rebuild()


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0040_add_hierarchical_and_admin_orgs"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
