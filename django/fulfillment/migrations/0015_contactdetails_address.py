# Generated by Django 3.0.1 on 2019-12-22 17:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fulfillment", "0014_repairbooking"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactdetails",
            name="address",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
    ]