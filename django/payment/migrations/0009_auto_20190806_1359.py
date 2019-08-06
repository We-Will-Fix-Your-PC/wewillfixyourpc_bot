# Generated by Django 2.2.1 on 2019-08-06 13:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0008_auto_20190804_1112'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='payment_method',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='paymentitem',
            name='quantity',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
