"""
Signals relating to swcomments.
"""
from django.dispatch import Signal

# Right after comment was saved (includes request for convenience)
comment_saved = Signal(providing_args=["comment", "request"])

