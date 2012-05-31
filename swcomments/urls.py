#urls
from django.conf.urls.defaults import *
import settings

urlpatterns = patterns('swcomments.views',
  url(r'^post-comment/$', 'post_comment', name='swcomments_post_comment'),
)

