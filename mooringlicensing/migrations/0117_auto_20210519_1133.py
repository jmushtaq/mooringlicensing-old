# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-05-19 03:33
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0116_auto_20210518_1120'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vesselownership',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
