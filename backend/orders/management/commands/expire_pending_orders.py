from django.core.management.base import BaseCommand

from orders.services import expire_pending_orders


class Command(BaseCommand):
    help = 'Cancel unpaid orders older than ORDER_EXPIRY_MINUTES and release their reserved stock.'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=None)

    def handle(self, *args, **options):
        cancelled = expire_pending_orders(options['minutes'])
        self.stdout.write(self.style.SUCCESS(f'Cancelled {cancelled} expired order(s).'))
