# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-08-05 01:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0200_auto_20210802_1539'),
    ]

    operations = [
        migrations.AddField(
            model_name='stickerprintingresponse',
            name='imported_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
