from celery import shared_task

from .services import expire_pending_orders as _expire_pending_orders


@shared_task
def expire_pending_orders():
    return {'cancelled': _expire_pending_orders()}
