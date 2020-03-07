# Generated by Django 3.0.3 on 2020-03-07 17:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("operator_interface", "0048_auto_20200305_0952"),
        ("twitter", "0004_accountlinkingstate"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountlinkingstate",
            name="conversation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="twitter_account_linking_state",
                to="operator_interface.ConversationPlatform",
            ),
        )
    ]
