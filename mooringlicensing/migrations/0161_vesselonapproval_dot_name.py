# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-06-21 05:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0160_auto_20210621_1115'),
    ]

    operations = [
        migrations.AddField(
            model_name='vesselonapproval',
            name='dot_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
