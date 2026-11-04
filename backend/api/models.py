import uuid
from django.conf import settings
from django.db import models


class Restaurant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    initial_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, editable=False, related_name='founded_restaurants')


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Dueño'
        ADMIN = 'ADMIN', 'Administrador'
        CASHIER = 'CASHIER', 'Caja'
        WAITER = 'WAITER', 'Mesero'
        KITCHEN = 'KITCHEN', 'Cocina'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    role = models.CharField(max_length=16, choices=Role.choices)
    is_active = models.BooleanField(default=True)


class AccessToken(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()


class AuditLog(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Zone(models.Model):
    # RF-012: canonical name enforces uniqueness inside each restaurant.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    name_key = models.CharField(max_length=100, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['restaurant', 'name_key'], name='zone_restaurant_name_unique')]


class Category(models.Model):
    # RF-023: categories and their comparison keys belong to one restaurant.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    name_key = models.CharField(max_length=300, editable=False)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ['position', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['restaurant', 'name_key'], name='category_restaurant_name_unique'),
            models.CheckConstraint(condition=~models.Q(name_key=''), name='category_name_key_not_empty'),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.name_key = self.name.casefold()
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'name', 'name_key'}
        return super().save(*args, **kwargs)


class Table(models.Model):
    # RF-013: restaurant ownership follows the protected zone relation.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    name_key = models.CharField(max_length=300, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(name=''), name='table_name_not_empty'),
            models.CheckConstraint(condition=~models.Q(name_key=''), name='table_name_key_not_empty'),
            models.UniqueConstraint(fields=['zone', 'name_key'], name='table_zone_name_unique'),
        ]

    def save(self, *args, **kwargs):
        # RF-016: keep the comparison key synchronized for ordinary ORM writes.
        self.name_key = self.name.strip().casefold()
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'name_key'}
        return super().save(*args, **kwargs)


class Product(models.Model):
    # RF-024: restaurant ownership is derived exclusively from the protected category.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField()

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0), name='product_price_nonnegative')]


class PaymentMethod(models.Model):
    # RF-020: configuration belongs exclusively to the authorized restaurant.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)


class OperationReason(models.Model):
    # RF-021: operation types come from the requirement; reason text is tenant configuration.
    class OperationType(models.TextChoices):
        CANCELLATION = 'CANCELLATION', 'Cancelación'
        MODIFICATION = 'MODIFICATION', 'Modificación'
        WASTE = 'WASTE', 'Desperdicio'
        RETURN = 'RETURN', 'Devolución'
        VOID = 'VOID', 'Anulación'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    operation_type = models.CharField(max_length=16, choices=OperationType.choices)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(operation_type__in=['CANCELLATION', 'MODIFICATION', 'WASTE', 'RETURN', 'VOID']),
            name='reason_valid_operation_type')]
