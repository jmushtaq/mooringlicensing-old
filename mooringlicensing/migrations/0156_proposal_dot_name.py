# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-06-16 02:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0155_auto_20210615_1415'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='dot_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
