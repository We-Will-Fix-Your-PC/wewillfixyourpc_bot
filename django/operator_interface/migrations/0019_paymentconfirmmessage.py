# Generated by Django 2.2.1 on 2019-08-06 13:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("operator_interface", "0018_auto_20190805_2029")]

    operations = [
        migrations.CreateModel(
            name="PaymentConfirmMessage",
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
                    "message",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="operator_interface.Message",
                    ),
                ),
            ],
        )
    ]
