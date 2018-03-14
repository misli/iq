from django.core.management.base import BaseCommand

from iq.utils import set_last_id

class Command(BaseCommand):
    help = 'Set last id.'

    def handle(self, *args, **options):
        set_last_id()
