# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-09-06 01:53
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0240_feeseason_application_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationtype',
            name='fee_by_fee_constructor',
            field=models.BooleanField(default=True),
        ),
    ]
