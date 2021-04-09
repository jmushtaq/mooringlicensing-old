# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-09 01:23
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0068_merge_20210409_0850'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationfee',
            name='fee_constructor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='application_fees', to='mooringlicensing.FeeConstructor'),
        ),
    ]
