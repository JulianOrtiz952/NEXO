from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def identify_initial_owners(apps, schema_editor):
    # RF-007: use historical evidence; never guess from current roles or IDs.
    Restaurant = apps.get_model('api', 'Restaurant')
    Membership = apps.get_model('api', 'Membership')
    AuditLog = apps.get_model('api', 'AuditLog')
    alias = schema_editor.connection.alias
    for restaurant in Restaurant.objects.using(alias).all():
        event = AuditLog.objects.using(alias).filter(
            restaurant_id=restaurant.pk, action__in=['restaurant.created', 'restaurant.owner_assigned'],
        ).order_by('created_at', 'pk').first()
        owner_id = (event.after.get('owner') if event.action == 'restaurant.created' else event.entity_id) if event else None
        if not owner_id or not Membership.objects.using(alias).filter(restaurant_id=restaurant.pk, user_id=owner_id).exists():
            raise RuntimeError(f'RF-007: falta evidencia del primer Dueño de {restaurant.pk}; requiere decisión del usuario.')
        if not Membership.objects.using(alias).filter(restaurant_id=restaurant.pk, role='OWNER', is_active=True, user__is_active=True, user__is_superuser=False).exists():
            raise RuntimeError(f'RF-007: {restaurant.pk} no tiene un Dueño activo; requiere regularización aprobada.')
        restaurant.initial_owner_id = owner_id
        restaurant.save(using=alias, update_fields=['initial_owner'])


class Migration(migrations.Migration):
    dependencies = [('api', '0002_auditlog'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(
            model_name='restaurant', name='initial_owner',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                                    null=True, editable=False, related_name='founded_restaurants'),
        ),
        migrations.RunPython(identify_initial_owners, migrations.RunPython.noop),
    ]
