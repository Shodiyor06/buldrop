"""Create clearly-labelled DEMO catalog data so the storefront works out of the box.

Opt-in only (never runs from a migration). Prices are placeholders: replace them with your real,
authorised products in Django admin before selling anything.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Product, ProductVariant, Supplier
from games.models import Category, Game
from inventory.models import InventoryAsset

TOPUPS = [
    ('pubg-mobile', 'PUBG Mobile UC', [('60 UC', 'pubg-uc-60', '12000'), ('325 UC', 'pubg-uc-325', '60000'), ('660 UC', 'pubg-uc-660', '120000')]),
    ('free-fire', 'Free Fire Diamonds', [('100 Diamonds', 'ff-d-100', '11000'), ('310 Diamonds', 'ff-d-310', '32000'), ('520 Diamonds', 'ff-d-520', '53000')]),
    ('roblox', 'Roblox Robux', [('400 Robux', 'rbx-400', '75000'), ('800 Robux', 'rbx-800', '145000')]),
]
CODE_PRODUCTS = [
    ('dota-2', 'Dota 2 Gift Code (DEMO)', 'dota2-gift-code-demo', '45000', 3),
    ('cs2', 'CS2 Prime Gift Code (DEMO)', 'cs2-gift-code-demo', '99000', 3),
]


class Command(BaseCommand):
    help = 'Create demo suppliers, products, variants and placeholder inventory codes (idempotent).'

    @transaction.atomic
    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(slug='games', defaults={'name': 'Games'})
        supplier, _ = Supplier.objects.get_or_create(
            slug='demo-operator',
            defaults={'name': 'Demo operator (manual fulfilment)', 'code': 'demo-operator', 'provider_type': 'manual'},
        )

        created = 0
        for game_slug, product_name, variants in TOPUPS:
            game = Game.objects.filter(slug=game_slug).first()
            if game is None:
                game = Game.objects.create(name=game_slug.replace('-', ' ').title(), slug=game_slug, category=category)
            product, was_created = Product.objects.get_or_create(
                slug=f'{game_slug}-topup-demo',
                defaults={
                    'game': game, 'supplier': supplier, 'name': f'{product_name} (DEMO)',
                    'description': 'Demo top-up. Fulfilled manually by an operator after payment. Replace with a real product.',
                    'price': Decimal('0'), 'currency': 'UZS', 'fulfillment_type': Product.FULFILLMENT_TOPUP,
                },
            )
            created += int(was_created)
            for name, sku, price in variants:
                ProductVariant.objects.get_or_create(
                    sku=sku, defaults={'product': product, 'name': name, 'price': Decimal(price), 'currency': 'UZS'},
                )

        for game_slug, name, slug, price, count in CODE_PRODUCTS:
            game = Game.objects.filter(slug=game_slug).first()
            if game is None:
                continue
            product, was_created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    'game': game, 'supplier': supplier, 'name': name,
                    'description': 'Demo digital code, delivered instantly after payment. Codes below are placeholders.',
                    'price': Decimal(price), 'currency': 'UZS', 'fulfillment_type': Product.FULFILLMENT_INVENTORY,
                },
            )
            created += int(was_created)
            if was_created:
                for index in range(1, count + 1):
                    InventoryAsset.objects.create(
                        product=product,
                        external_id=f'{slug}-{index}',
                        metadata={'code': f'DEMO-{slug.upper()[:6]}-{index:04d}', 'instructions': 'Demo code, not redeemable.'},
                    )

        self.stdout.write(self.style.SUCCESS(f'Demo catalog ready ({created} new product(s)).'))
        self.stdout.write('Replace demo products and prices with real ones in Django admin before going live.')
