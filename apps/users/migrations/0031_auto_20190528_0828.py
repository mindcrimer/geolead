# Generated by Django 2.2.1 on 2019-05-28 08:28

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0030_user_total_report_users'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='total_report_users',
        ),
        migrations.AlterField(
            model_name='user',
            name='last_name',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Фамилия ответствен   ного лица'),
        ),
        migrations.CreateModel(
            name='UserTotalReportUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('ordering', models.IntegerField(db_index=True, default=0, verbose_name='Порядок')),
                ('status', models.SmallIntegerField(choices=[(0, 'Черновик'), (1, 'Публичный'), (2, 'Скрытый')], default=1, verbose_name='Статус')),
                ('executor_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='total_report_companies', to=settings.AUTH_USER_MODEL, verbose_name='Получатель отчета')),
                ('report_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='total_report_executors', to=settings.AUTH_USER_MODEL, verbose_name='Аккаунт, по которому составляется отчет')),
            ],
            options={
                'verbose_name': 'Подчиненная компания для сводных отчетов',
                'verbose_name_plural': 'Подчиненные компании для сводных отчетов',
                'ordering': ('ordering',),
            },
        ),
    ]
