from django.core.management.base import BaseCommand

from iq.utils import check_account

class Command(BaseCommand):
    help = 'Check account.'

    def handle(self, *args, **options):
        check_account()
