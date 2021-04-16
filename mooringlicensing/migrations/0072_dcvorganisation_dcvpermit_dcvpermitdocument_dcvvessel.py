# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-14 00:26
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import mooringlicensing.components.approvals.models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0071_merge_20210412_1108'),
    ]

    operations = [
        migrations.CreateModel(
            name='DcvOrganisation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True)),
                ('abn', models.CharField(blank=True, max_length=50, null=True, verbose_name='ABN')),
            ],
        ),
        migrations.CreateModel(
            name='DcvPermit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lodgement_number', models.CharField(blank=True, default='', max_length=9)),
                ('status', models.CharField(choices=[('current', 'Current'), ('expired', 'Expired')], default='current', max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name='DcvPermitDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=255, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('uploaded_date', models.DateTimeField(auto_now_add=True)),
                ('_file', models.FileField(max_length=512, upload_to=mooringlicensing.components.approvals.models.update_dcv_permit_doc_filename)),
                ('can_delete', models.BooleanField(default=False)),
                ('dcv_permit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permits', to='mooringlicensing.DcvPermit')),
            ],
        ),
        migrations.CreateModel(
            name='DcvVessel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rego_no', models.CharField(blank=True, max_length=200, null=True, unique=True)),
                ('uiv_vessel_identifier', models.CharField(blank=True, max_length=10, null=True, unique=True)),
                ('vessel_name', models.CharField(blank=True, max_length=400)),
                ('dcv_organisation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='mooringlicensing.DcvOrganisation')),
            ],
        ),
    ]
