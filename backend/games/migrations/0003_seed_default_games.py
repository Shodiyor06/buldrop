from django.db import migrations


DEFAULT_GAMES = [
    ('CS2', 'cs2', 'Counter-Strike 2 digital goods. Only products with authorized sourcing should be listed.'),
    ('PUBG Mobile', 'pubg-mobile', 'PUBG Mobile top-ups and supported digital goods.'),
    ('Free Fire', 'free-fire', 'Free Fire top-ups and supported digital goods.'),
    ('Roblox', 'roblox', 'Only products offered by an authorized, verified supplier may be listed.'),
    ('Dota 2', 'dota-2', 'Dota 2 digital goods. Availability depends on authorized supply.'),
]


def add_default_games(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    for name, slug, description in DEFAULT_GAMES:
        Game.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'description': description, 'is_active': True},
        )


class Migration(migrations.Migration):
    dependencies = [('games', '0002_gameaccount')]

    operations = [migrations.RunPython(add_default_games, migrations.RunPython.noop)]
