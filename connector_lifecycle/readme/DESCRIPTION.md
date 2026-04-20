This addon provides generic queue-backed lifecycle helpers for connector
inbound and outbound synchronization flows.

It owns reusable listeners, schedulers, dispatchers, and binding helpers that
transport-specific addons can feed into without coupling the synchronization
engine to a specific ingress mechanism.