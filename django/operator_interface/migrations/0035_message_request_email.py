# Generated by Django 2.2.4 on 2019-09-01 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('operator_interface', '0034_auto_20190901_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='request_email',
            field=models.BooleanField(default=False, null=True),
        ),
    ]
