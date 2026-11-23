# Support endpoints live with the order models; re-exported here for the `support` app namespace.
from orders.views import SupportTicketDetailView, SupportTicketListView

__all__ = ['SupportTicketDetailView', 'SupportTicketListView']
