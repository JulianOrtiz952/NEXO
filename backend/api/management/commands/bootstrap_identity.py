from getpass import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction


class Command(BaseCommand):
    help = 'Crea una identidad inicial sin contraseña hardcodeada (RF-003, RF-005).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--platform-admin', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        email = options['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError('Este correo ya está registrado.')
        password = getpass('Contraseña: ')
        if password != getpass('Confirma la contraseña: '):
            raise CommandError('Las contraseñas no coinciden.')
        user = User(username=email, email=email)
        try:
            validate_password(password, user)
            user.full_clean(exclude=['password'])
        except ValidationError as exc:
            raise CommandError(str(exc))
        with transaction.atomic():
            user.is_superuser = options['platform_admin']
            user.set_password(password)
            user.save()
        self.stdout.write(self.style.SUCCESS(f'Identidad creada: {user.pk}.'))
