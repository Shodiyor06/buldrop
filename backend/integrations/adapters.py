import os


class MockProviderAdapter:
    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or ''
        self.api_url = api_url or os.getenv('PLAYPAY_API_URL', 'https://playpay.uz/app/api')

    def get_catalog(self):
        return [{'id': 'test-mock-uc', 'name': 'Test UC package', 'type': 'topup', 'mode': 'test'}]

    def validate_player(self, player_id, game_slug):
        return {
            'valid': None,
            'verification': 'unavailable',
            'player_id': player_id,
            'game_slug': game_slug,
            'mode': 'test',
        }

    def create_order(self, details):
        return {
            'provider_order_id': 'TEST-MOCK',
            'status': 'simulated',
            'delivered': False,
            'details': details,
        }

    def check_order_status(self, provider_order_id):
        return {'provider_order_id': provider_order_id, 'status': 'simulated', 'delivered': False}


class SkinProvider:
    def get_catalog(self):
        raise NotImplementedError

    def check_availability(self, external_id):
        raise NotImplementedError

    def reserve(self, external_id, order_reference):
        raise NotImplementedError

    def get_trade_status(self, provider_trade_id):
        raise NotImplementedError


class MockSkinProvider(SkinProvider):
    def get_catalog(self):
        return []

    def check_availability(self, external_id):
        return {'external_id': external_id, 'available': False, 'mode': 'mock'}

    def reserve(self, external_id, order_reference):
        return {
            'external_id': external_id,
            'order_reference': order_reference,
            'status': 'not_configured',
            'delivered': False,
        }

    def get_trade_status(self, provider_trade_id):
        return {'provider_trade_id': provider_trade_id, 'status': 'not_configured', 'delivered': False}
