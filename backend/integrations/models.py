from django.db import models
from django.db.models import Q


class IntegrationEvent(models.Model):
    STATUS_RECEIVED = 'received'
    STATUS_PROCESSED = 'processed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_FAILED, 'Failed'),
    ]

    provider = models.CharField(max_length=80)
    event_type = models.CharField(max_length=120)
    external_id = models.CharField(max_length=180, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'external_id'],
                condition=~Q(external_id=''),
                name='unique_provider_external_event',
            ),
        ]

    def __str__(self):
        return f'{self.provider}: {self.event_type}'
