"""Bulk-load digital codes for an inventory product from a text file (one code per line)."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Product
from inventory.models import InventoryAsset


class Command(BaseCommand):
    help = 'Import inventory codes: manage.py import_inventory <product-slug> codes.txt [--instructions "..."]'

    def add_arguments(self, parser):
        parser.add_argument('product_slug')
        parser.add_argument('file')
        parser.add_argument('--instructions', default='')

    @transaction.atomic
    def handle(self, *args, **options):
        product = Product.objects.filter(slug=options['product_slug']).first()
        if product is None:
            raise CommandError(f"Product '{options['product_slug']}' does not exist.")
        if product.fulfillment_type != Product.FULFILLMENT_INVENTORY:
            raise CommandError('The product must use the "inventory" fulfilment type.')
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'File not found: {path}')

        created = skipped = 0
        for line in path.read_text(encoding='utf-8').splitlines():
            code = line.strip()
            if not code:
                continue
            _, was_created = InventoryAsset.objects.get_or_create(
                product=product,
                external_id=code[:120],
                defaults={'metadata': {'code': code, 'instructions': options['instructions']}},
            )
            created += int(was_created)
            skipped += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f'Imported {created} code(s), skipped {skipped} duplicate(s).'))
