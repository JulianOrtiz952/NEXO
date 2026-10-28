from django.db import migrations, models


def assign_existing_names(apps, schema_editor):
    # RF-015: approved initial names per zone; preserve UUIDs, dates and audit.
    Table = apps.get_model('api', 'Table')
    database = schema_editor.connection.alias
    previous_zone = None
    number = 0
    for table in Table.objects.using(database).order_by('zone_id', 'created_at', 'pk').iterator():
        if table.zone_id != previous_zone:
            previous_zone = table.zone_id
            number = 0
        number += 1
        Table.objects.using(database).filter(pk=table.pk).update(name=f'Mesa {number}')


class Migration(migrations.Migration):
    dependencies = [('api', '0005_table')]
    operations = [
        migrations.AddField(model_name='table', name='name', field=models.CharField(max_length=100, null=True)),
        migrations.RunPython(assign_existing_names, migrations.RunPython.noop),
        migrations.AlterField(model_name='table', name='name', field=models.CharField(max_length=100)),
        migrations.AddConstraint(model_name='table', constraint=models.CheckConstraint(condition=~models.Q(name=''), name='table_name_not_empty')),
    ]
