# Generated by Django 2.2.1 on 2019-08-12 20:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('operator_interface', '0023_auto_20190812_1924'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='delivered',
            field=models.BooleanField(default=False),
        ),
    ]
