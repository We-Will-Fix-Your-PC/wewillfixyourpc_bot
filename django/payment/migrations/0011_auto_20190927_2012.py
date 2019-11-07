# Generated by Django 2.2.5 on 2019-09-27 20:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0010_auto_20190808_1958'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payment',
            name='customer',
        ),
        migrations.AddField(
            model_name='payment',
            name='customer_id',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name='Customer',
        ),
    ]
