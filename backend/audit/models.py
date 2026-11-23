from django.db import models


class AuditLog(models.Model):
    actor = models.CharField(max_length=120, blank=True, default='')
    action = models.CharField(max_length=160)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
