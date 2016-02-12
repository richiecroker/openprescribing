# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-10 17:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0040_auto_20160204_1720'),
    ]

    operations = [
        migrations.AddField(
            model_name='pct',
            name='address',
            field=models.CharField(blank=True, max_length=400, null=True),
        ),
        migrations.AddField(
            model_name='pct',
            name='close_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pct',
            name='open_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pct',
            name='postcode',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]