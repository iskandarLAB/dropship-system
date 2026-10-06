from django.conf import settings


class GatewayError(Exception):
    pass


class InvalidSignature(GatewayError):
    pass


def get_gateway(name=None):
    name = name or settings.PAYMENT_GATEWAY
    if name == "chip":
        from .chip import ChipGateway

        return ChipGateway()
    if name == "dummy":
        from .dummy import DummyGateway

        return DummyGateway()
    raise GatewayError(f"Unknown payment gateway: {name}")
