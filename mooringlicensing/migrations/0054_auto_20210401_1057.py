# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-01 02:57
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0053_auto_20210401_1046'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Fee',
            new_name='FeeItem',
        ),
    ]
