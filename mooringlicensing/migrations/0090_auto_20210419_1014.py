# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-19 02:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0089_proposal_percentage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vesselownership',
            name='percentage',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
