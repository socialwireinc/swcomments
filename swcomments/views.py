from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseServerError, HttpResponseBadRequest, Http404
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import simplejson, safestring
from django.views.decorators.http import require_POST
#from django.contrib.auth.decorators import login_required
#from django.contrib.auth import models as authmodels
#from django.contrib.contenttypes import models as ctmodels

import swcomments

FORM_TEMPLATES = [
  "%(app_label)s/%(model)s_%(objmodel)s/%(template_name)s",
  "%(app_label)s/%(model)s_%(objmodel)s_%(template_name)s",
  "%(app_label)s/%(model)s/%(template_name)s",
  "%(app_label)s/%(model)s_%(template_name)s",
  "%(app_label)s/%(template_name)s",
  "%(template_name)s"   # Urgh
]

@require_POST
def post_comment(request):
  """
  Post a comment.  This view currently only supports AJAX posting.

  AJAX call returns JSON structure:
  
  {
    rc: "CODE"
    [, cid: COMMENTID ]
    [, content: "..." ]
    [, errors: [...] ]
    [, errormsg: "MSG" ]
  }

  Where:
  - rc=success: saved successfully ('cid' is set to commentid)
    - cid: commentid (int) on successful save
  - rc=failure: failure saving comment ('content' and 'errors' is set)
    - content: HTML rendering of form with error messages
    - errors: json structure of errors
  - rc=error: misc. error saving form ('errormsg' is server error msg)
    - errormsg: string with server's error message in case of a misc failure
  """

  import time
  time.sleep(.5)

  #if not request.is_ajax():
  #  raise NotImplementedError('View currently only support AJAX requests')

  # Identify Comment type (fetch actual Comment model class)
  comment_model = request.POST.get('comment_model')
  if not comment_model:
    return HttpResponseBadRequest('Could not identify comment_model field')
  try:
    #ctmodel = ctmodels.ContentType.objects.get_by_natural_key(*comment_model.split(".", 1))
    #CommentClass = ctmodel.model_class()  
    ModelClass = models.get_model(*comment_model.split(".", 1))
  except Exception, e:
    return HttpResponseBadRequest('Could not find ContentType for Comment model: %s' % (comment_model,))

  # Identify comment content object
  content_type = request.POST.get('content_type')
  try:
    object_pk = int(request.POST.get('object_pk'))
  except:
    object_pk = 0
  if not object_pk or not content_type:
    return HttpResponseBadRequest('Could not identify content_type and/or object_pk field')
  try:
    #ctmodel = ctmodels.ContentType.objects.get_by_natural_key(*content_type.split(".", 1))
    #ContentObjectClass = ctmodel.model_class()
    ContentObjectClass = models.get_model(*content_type.split(".", 1))
  except Exception, e:
    return HttpResponseBadRequest('Could not find ContentType for Content object: %s' % (content_type,))

  # Fetch content_object
  obj = ContentObjectClass.objects.get(pk=object_pk)

  # Create form
  FormClass = ModelClass.get_form_class()
  form = FormClass(obj, data=request.POST)

  if form.is_valid():
    c = ModelClass(**form.get_model_data())
    c.user = request.user
    c.save()

    swcomments.signals.comment_saved.send(sender=c.__class__, comment=c, request=request)

    return HttpResponse(simplejson.dumps({ 'rc': "success", 'cid': c.id }), mimetype="application/json")


  # Create list of templates
  template_name = form.decode_template_name(form.data['tn']) or "form.html"
  o_name = obj._meta.object_name.lower()
  app_label, model = ModelClass.get_nonproxy_model_name()
  _d = dict(app_label=app_label, model=model, objmodel=o_name, template_name=template_name)
  templates = [ _s % _d for _s in FORM_TEMPLATES ]

  # Render first template we find
  s = render_to_string(templates, { 'form': form, 'object': obj }, context_instance=RequestContext(request))
  
  resp = dict(
    rc="failure",
    content=s,
    errors=form.errors,
  )
  return HttpResponse(simplejson.dumps(resp), mimetype="application/json")

