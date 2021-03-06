# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-08-16 08:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0208_remove_dcvvessel_uvi_vessel_identifier'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProofOfIdentityDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=255, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('uploaded_date', models.DateTimeField(auto_now_add=True)),
                ('_file', models.FileField(max_length=512, upload_to='')),
                ('input_name', models.CharField(blank=True, max_length=255, null=True)),
                ('can_delete', models.BooleanField(default=True)),
                ('can_hide', models.BooleanField(default=False)),
                ('hidden', models.BooleanField(default=False)),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proof_of_identity_documents', to='mooringlicensing.Proposal')),
            ],
            options={
                'verbose_name': 'Proof Of Identity',
            },
        ),
        migrations.CreateModel(
            name='SignedLicenceAgreementDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=255, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('uploaded_date', models.DateTimeField(auto_now_add=True)),
                ('_file', models.FileField(max_length=512, upload_to='')),
                ('input_name', models.CharField(blank=True, max_length=255, null=True)),
                ('can_delete', models.BooleanField(default=True)),
                ('can_hide', models.BooleanField(default=False)),
                ('hidden', models.BooleanField(default=False)),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signed_licence_agreement_documents', to='mooringlicensing.Proposal')),
            ],
            options={
                'verbose_name': 'Signed Licence Agreement',
            },
        ),
    ]
