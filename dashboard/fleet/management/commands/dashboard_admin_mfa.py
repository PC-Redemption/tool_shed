from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Begin or confirm TOTP enrollment for an existing dashboard staff maintainer."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("begin", "confirm"))
        parser.add_argument("--username", required=True)
        parser.add_argument("--token")

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"], is_active=True, is_staff=True).first()
        if user is None:
            raise CommandError("an active staff maintainer with that username does not exist")
        if options["action"] == "begin":
            TOTPDevice.objects.filter(user=user, confirmed=False, name="primary").delete()
            device = TOTPDevice.objects.create(user=user, name="primary", confirmed=False)
            self.stdout.write("Scan this one-time TOTP provisioning URI, then run confirm:")
            self.stdout.write(device.config_url)
            return
        token = options.get("token")
        if not token or not token.isdigit():
            raise CommandError("confirm requires --token with the current numeric TOTP code")
        device = TOTPDevice.objects.filter(user=user, confirmed=False, name="primary").order_by("-id").first()
        if device is None or not device.verify_token(int(token)):
            raise CommandError("the TOTP code was not accepted")
        device.confirmed = True
        device.save(update_fields=("confirmed",))
        self.stdout.write("dashboard maintainer MFA: confirmed")
