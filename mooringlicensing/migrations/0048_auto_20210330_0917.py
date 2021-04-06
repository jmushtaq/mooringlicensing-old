# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-03-30 01:17
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0047_vesselsizecategorygroup'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeeConstructor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('application_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='mooringlicensing.ApplicationType')),
                ('fee_season', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='mooringlicensing.FeeSeason')),
                ('vessel_size_category_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='mooringlicensing.VesselSizeCategoryGroup')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='feeconstructor',
            unique_together=set([('application_type', 'fee_season')]),
        ),
    ]
