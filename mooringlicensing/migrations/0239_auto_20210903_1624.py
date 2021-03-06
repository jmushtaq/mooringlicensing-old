# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-09-03 08:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0238_auto_20210902_0945'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='dot_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='customer_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('with_assessor', 'Under Review'), ('awaiting_endorsement', 'Awaiting Endorsement'), ('awaiting_documents', 'Awaiting Documents'), ('printing_sticker', 'Printing Sticker'), ('approved', 'Approved'), ('declined', 'Declined'), ('discarded', 'Discarded'), ('awaiting_payment', 'Awaiting Payment'), ('awaiting_sticker_returned', 'Awaiting Sticker Returned'), ('expired', 'Expired')], default='draft', max_length=40, verbose_name='Customer Status'),
        ),
    ]
