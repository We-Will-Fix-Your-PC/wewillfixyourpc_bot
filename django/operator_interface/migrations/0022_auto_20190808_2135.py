# Generated by Django 2.2.1 on 2019-08-08 21:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('operator_interface', '0021_auto_20190807_0630'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='customer_gender',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='conversation',
            name='customer_locale',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
