from django.db import migrations, models


def populate_keys(apps, schema_editor):
    # RF-016: fail before backfill when existing names collide; never rename data.
    Table = apps.get_model('api', 'Table')
    rows = Table.objects.using(schema_editor.connection.alias)
    seen = set()
    for table in rows.only('zone_id', 'name').iterator():
        key = (table.zone_id, table.name.strip().casefold())
        if key in seen or not key[1]:
            raise RuntimeError('RF-016: existen nombres de mesa duplicados o vacíos en una zona. Revisa y corrige los nombres antes de aplicar esta migración.')
        seen.add(key)
    for table in rows.only('name').iterator():
        rows.filter(pk=table.pk).update(name_key=table.name.strip().casefold())


class Migration(migrations.Migration):
    dependencies = [('api', '0006_table_name')]
    operations = [
        migrations.AddField(model_name='table', name='name_key', field=models.CharField(max_length=300, editable=False, null=True)),
        migrations.RunPython(populate_keys, migrations.RunPython.noop),
        migrations.AlterField(model_name='table', name='name_key', field=models.CharField(max_length=300, editable=False)),
        migrations.AddConstraint(model_name='table', constraint=models.CheckConstraint(condition=~models.Q(name_key=''), name='table_name_key_not_empty')),
        migrations.AddConstraint(model_name='table', constraint=models.UniqueConstraint(fields=('zone', 'name_key'), name='table_zone_name_unique')),
    ]
