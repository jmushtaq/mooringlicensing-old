# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-08-17 04:21
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0211_stickerprintingresponse_sticker_printing_response_email'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='email_body',
        ),
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='email_date',
        ),
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='email_from',
        ),
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='email_message_id',
        ),
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='email_subject',
        ),
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='imported_datetime',
        ),
        migrations.RemoveField(
            model_name='stickerprintingresponse',
            name='received_datetime',
        ),
    ]
