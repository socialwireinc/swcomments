import django_setup

from django.contrib.auth import models as usermodels
from django.contrib.sites import models as sitemodels
from django.contrib.contenttypes import models as ctmodels

from swcomments import models as cmodels
from engine import models

site = sitemodels.Site.objects.get_current()
o = list(models.ServiceProfile.objects.all())[-1]
u = usermodels.User.objects.get(username='marc')

print "Using site: %s" % (site,)
print "Using object: %s (%s)" % (o, o.__class__)
print "Using user: %s" % (u,)

q = cmodels.QuestionComment(user=u, content_object=o, title='I have a question...')
q.save()

a = cmodels.AnswerComment(user=u, content_object=o, title='Answer is...', question=q)
a.save()

