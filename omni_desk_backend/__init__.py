from __future__ import absolute_import, unicode_literals

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app,
# and it will be available as 'celery' on the package.
from .omni_desk_backend.celery import app as celery

__all__ = ('celery',)