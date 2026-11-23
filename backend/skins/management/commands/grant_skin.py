from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import InventoryAsset
from skins.services import grant_skin


class Command(BaseCommand):
    help = 'Move an available inventory asset of a skin product into a user inventory (for testing or compensation).'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('product_slug')

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError('User not found.') from exc
        asset = (
            InventoryAsset.objects.select_for_update()
            .filter(product__slug=options['product_slug'], product__is_skin=True, status=InventoryAsset.STATUS_AVAILABLE)
            .order_by('id').first()
        )
        if asset is None:
            raise CommandError('No available asset for that skin product (is the product marked as a skin?).')
        asset.status = InventoryAsset.STATUS_SOLD
        asset.save(update_fields=['status', 'updated_at'])
        skin = grant_skin(user=user, asset=asset)
        self.stdout.write(self.style.SUCCESS(f'Skin #{skin.pk} granted to {user.username}.'))
