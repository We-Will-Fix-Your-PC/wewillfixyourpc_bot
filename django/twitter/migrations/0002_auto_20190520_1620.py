# Generated by Django 2.2.1 on 2019-05-20 16:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("twitter", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="config",
            name="auth",
            field=models.TextField(blank=True, null=True),
        )
    ]
