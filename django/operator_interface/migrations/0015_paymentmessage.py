# Generated by Django 2.2.1 on 2019-08-02 15:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("operator_interface", "0014_remove_conversation_noonce")]

    operations = [
        migrations.CreateModel(
            name="PaymentMessage",
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
                ("payment_id", models.CharField(max_length=255)),
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
