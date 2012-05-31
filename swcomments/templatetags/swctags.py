"""
Template tags for swcomments application.

"""

from django import template
from django.contrib.contenttypes import models as ctmodels
from django.db import models as dbmodels
from django.db.models.query import QuerySet

from swcomments import models, views

register = template.Library()

def remove_quotes(s):
  """
  Checks if string is encased in quotes (single or double).  If so, returns string WITHOUT
  quotes.
  """
  if not s: return
  if s[0] in ["'", '"'] and s[-1] in ["'", '"']:
    return s[1:-1]
  return s

class SWCommentsBaseNode(template.Node):
  """
  Base template node for swcomments_get_list, swcomments_get_count and swcomments_render_list.
  """
  def __init__(self, model, o_expr, filter=None, order=None, **kw):
    """
    Besides for o_expr, model and filter (which is optional), all other params are 'custom' 
    and are the responsibility of the tag function to ensure that they are passed and set 
    properly (they will be added to this instance as-is).
    """
    self.o_expr = template.Variable(o_expr)
    self.filter = filter
    self.order = order and template.Variable(order) or None
    self.templatename = kw.get('templatename')
    model = model.lower()
    if '.' in model:
      self.app_label, self.model = model.split(".", 1)
    else:
      self.app_label, self.model = "swcomments", model
    #self.model_ct = ctmodels.ContentType.objects.get(app_label=self.app_label, model=self.model)
    #self.model_class = self.model_ct.model_class()
    self.model_class = dbmodels.get_model(self.app_label, self.model)
    if not issubclass(self.model_class, models.BaseComment):
      raise TypeError("The Comment model '%s' must be based on swcomments.BaseComment" % (self.model_class,))
    for k,v in kw.items():
      setattr(self, k, v)

  def _get_qs(self, o_expr, for_count=False, order=None):
    """
    Given a comment model (must be based on swcomments.BaseComment) and
    either a model instance or a queryset/list/tuple, return the queryset
    that can be used to retrieve comments and/or comment count for
    those objects.
    Applies filter if passed.
    If for_count is true, calls model's do_count with the queryset.
    """
    m = self.model_class
    if self.filter and hasattr(m, self.filter):
      qs = getattr(m, self.filter)
    else:
      qs = m.objects

    if isinstance(o_expr, (QuerySet, tuple, list)):
      o_list = list(o_expr)
      if o_list: 
        ct = ctmodels.ContentType.objects.get_for_model(o_list[0])
        pk = [ _.pk for _ in o_list ]
        qs = qs.filter(content_type=ct, object_pk__in=pk)
      else:
        qs = qs.none()
    else:
      ct = ctmodels.ContentType.objects.get_for_model(o_expr)
      pk = o_expr.pk
      qs = qs.filter(content_type=ct, object_pk=pk)

    if order:
      if hasattr(self.model_class, 'ORDER') and self.model_class.ORDER.get(order):
        qs = qs.order_by(self.model_class.ORDER.get(order))

    if for_count:
      qs = m.do_count(qs)

    return qs

  def render(self):
    """Dummy render method -- needs to be implemented by subclasses"""
    raise NotImplementedError()

class SWCommentsGetListNode(SWCommentsBaseNode):
  """
  Actual implementation of swcomments_get_list tag.
  """
  def _get_qs(self, *args, **kws):
    qs = super(SWCommentsGetListNode, self)._get_qs(*args, **kws)
    return qs#.order_by('submit_date') #XXX let models do this

  def render(self, context):
    o_expr = self.o_expr.resolve(context)
    order = self.order and self.order.resolve(context) or None
    context[self.varname] = self._get_qs(o_expr, order=order)
    return ''

class SWCommentsGetCountNode(SWCommentsBaseNode):
  """
  Actual implementation of swcomments_get_count tag.
  """
  def render(self, context):
    o_expr = self.o_expr.resolve(context)
    qs = self._get_qs(o_expr, for_count=True)  # Get query set (for count)
    context[self.varname] = qs.count()
    return ''

class SWCommentsGetListsNode(SWCommentsBaseNode):
  """
  Actual implementation of swcomments_get_lists tag.
  """
  def _get_qs(self, *args, **kws):
    qs = super(SWCommentsGetListsNode, self)._get_qs(*args, **kws)
    return qs#.order_by('submit_date')

  def render(self, context):
    o_expr = self.o_expr.resolve(context)
    d = {}
    for comment in self._get_qs(o_expr):
      o = comment.content_object
      if o not in d: d[o] = []
      d[o].append(comment)
    context[self.varname] = d
    return ''

class SWCommentsRenderListNode(SWCommentsBaseNode):
  """
  Actual implementation of swcomments_render_list tag.
  """
  def render(self, context):
    o_expr = self.o_expr.resolve(context)
    raise NotImplementedError("swcomments_render_list")
    return ''

class SWCommentsRenderFormNode(SWCommentsBaseNode):
  """
  Actual implementation of swcomments_render_list tag.
  """
  def render(self, context):
    # Make sure object passed is a model instance
    o = self.o_expr.resolve(context)
    if not isinstance(o, dbmodels.Model):
      raise TypeError("Object passed after 'for' must be a model instance")
  
    # Find template
    tn = (self.templatename or 'form.html') 
    o_name = type(o).__name__.lower()
    app_label, model = self.model_class.get_nonproxy_model_name()
    _d = dict(app_label=app_label, model=model, objmodel=o_name, template_name=tn)
    templates = [ _s % _d for _s in views.FORM_TEMPLATES ]
    t = template.loader.select_template(templates)

    # Create form
    form = self.model_class.get_form_class()(o, template_name=tn)

    # Create context (copy from existing to retain all variables that exist) and render
    context.push()
    context.update({
      'object': o,
      'form': form,
    })
    c = template.Context(context)
    html = t.render(c)
    context.pop()

    return html

def _parse(token, accept={}):
  """
  Common parsing code for swcomments_get_list, swcomments_get_count, swcomments_render_list...
  The 'accept' parameter is a dict of keyword:config values to look for in parsing.
  'config' is a dictionary that can contain:
  - 'name': name to return the value as (instead of keyword)
  - 'default': default value (None if not found)
  It can also be non, in which case name=keyword and default=None.
  """

  try:
    l = token.split_contents()
    tag_name, args = l[0], l[1:]
  except ValueError, e:
    tag_name = token.contents.split()[0]
    raise Exception(tag_name)

  d = {}

  while args:
    arg = args.pop(0).lower()
    if arg not in accept or not args:
      raise Exception(tag_name)
    param = remove_quotes(args.pop(0))
    cfg = accept[arg] or {}
    d[cfg.get('name', arg)] = param

  for kw, cfg in accept.items():
    name = cfg.get('name', kw)
    if name not in d:
      d[name] = cfg.get('default')

  return d

@register.tag
def swcomments_get_list(parser, token):
  """
  Usage:

    {% swcomments_get_list for [object_or_queryset] (of [model]) (as [varname]) (order [oname]) %}

  Sets a list 'varname' (default 'comment_list') in current context, of comment objects of type 'model' 
  (default swcomments.Comment) for the object (instance) or queryset/list of objects.

  Notes:
  - object_or_queryset can either be an instance of a model, or a queryset/list/tuple containing
    instance(s) of a model.  It may also be empty/None, in which case an empty list is returned.
  - model must be a valid comment model, ie based on swcomments.BaseComment.
  - in all cases above, 'model' does not need to include app_label (it is assumed to
    be swcomments).  If you need to include an app_label, the syntax is "app_label.model".
  """
  SYNTAX_EXCEPTION_STR = "%r tag syntax incorrect (requires a 'for [object_or_qs]', 'as [varname]', and optional 'of [model]')" 

  try:
    d = _parse(token, { 
      'for': { 'name': 'o_expr' }, 
      'of': { 'name': 'model', 'default': 'Comment' }, 
      'as': { 'name': 'varname' },
      'filter': { 'name': 'filter' },
      'order': { 'name': 'order' },
    })
  except Exception, e:
    raise template.TemplateSyntaxError(SYNTAX_EXCEPTION_STR % (str(e),))

  return SWCommentsGetListNode(**d)

@register.tag
def swcomments_get_count(parser, token):
  """
  Usage:

    {% swcomments_get_count for [object_or_queryset] (of [model]) (as [varname]) %}

  Sets a counter 'varname' (default 'comment_list') in current context, of comment objects of type 'model' 
  (default swcomments.Comment) for the object (instance) or queryset/list of objects.

  Notes:
  - object_or_queryset can either be an instance of a model, or a queryset/list/tuple containing
    instance(s) of a model.  It may also be empty/None, in which case an empty list is returned.
  - model must be a valid comment model, ie based on swcomments.BaseComment.
  - in all cases above, 'model' does not need to include app_label (it is assumed to
    be swcomments).  If you need to include an app_label, the syntax is "app_label.model".
  """
  SYNTAX_EXCEPTION_STR = "%r tag syntax incorrect (requires a 'for [object_or_qs]', 'as [varname]', and optional 'of [model]')" 

  try:
    d = _parse(token, { 
      'for': { 'name': 'o_expr' }, 
      'of': { 'name': 'model', 'default': 'Comment' }, 
      'as': { 'name': 'varname' },
      'filter': { 'name': 'filter' },
    })
  except Exception, e:
    raise template.TemplateSyntaxError(SYNTAX_EXCEPTION_STR % (str(e),))

  return SWCommentsGetCountNode(**d)

@register.tag
def swcomments_get_lists(parser, token):
  """
  Usage:

    {% swcomments_get_lists for [objects_or_queryset] (of [model]) (as [varname]) (order [oname]) %}

  Sets a dictionary 'varname' (default 'comment_dict') in current context, of comment objects of type 'model' 
  (default swcomments.Comment) for the object (instance) or queryset/list of objects.  The key for each list
  of comments is the object from the list of objects or queryset.

  Notes:
  - objects_or_queryset can either be a list/tuple of instances of a model, or a queryset/list/tuple containing
    instance(s) of a model.  It may also be empty/None/empty sequence, in which case an empty list is returned.
  - model must be a valid comment model, ie based on swcomments.BaseComment.
  - in all cases above, 'model' does not need to include app_label (it is assumed to
    be swcomments).  If you need to include an app_label, the syntax is "app_label.model".
  """
  SYNTAX_EXCEPTION_STR = "%r tag syntax incorrect (requires a 'for [objects_or_qs]', 'as [varname]', and optional 'of [model]')" 

  try:
    d = _parse(token, { 
      'for': { 'name': 'o_expr' }, 
      'of': { 'name': 'model', 'default': 'Comment' }, 
      'as': { 'name': 'varname' }, 
      'filter': { 'name': 'filter' },
      'order': { 'name': 'order' },
    })
  except Exception, e:
    raise template.TemplateSyntaxError(SYNTAX_EXCEPTION_STR % (str(e),))

  return SWCommentsGetListsNode(**d)

@register.tag
def swcomments_render_list(parser, token):
  """f
  Usage:
   
    {% swcomments_render_list for [object_or_queryset] (of [model]) (using [templatename]) %}

  renders a list of comments for 'object_or_queryset' of type 'model' (default 'swcomments.Comment').

  If a 'templatename' is included, it will be used (you may include a directory syntax
  such as 'myapp/commentlist.html').  Otherwise, looks for a template to render in this order:
  - swcomments/[model]_[qs_or_o_model]/list.html
  - swcomments/[model]/list.html
  - swcomments/list.html

  There will be a 'comment_list' variable made available to the template.
  """
  SYNTAX_EXCEPTION_STR = "%r tag syntax incorrect (requires a 'for [object_or_qs]', optional 'of [model]' and optional 'using [templatename]')" 

  raise NotImplementedError()

  try:
    d = _parse(token, { 'for': { 'name': 'o_expr' }, 'of': { 'name': 'model', 'default': 'Comment' }, 'using': { 'name': 'templatename' } })
  except:
    raise template.TemplateSyntaxError(SYNTAX_EXCEPTION_STR % (tag_name,))

  return SWCommentsRenderListNode(**d)

@register.tag
def swcomments_render_form(parser, token):
  """
  Usage:

    {% swcomments_render_form for [object] (of [model]) (using [templatename]) %}

  renders the form for object 'object' using the Form associated to model 'model' (default
  'swcomments.Comment').

  If a 'templatename' is included, it will be used (you may include a directory syntax
  such as 'myapp/form.html').  Otherwise, looks for a template to render in this order:
  - swcomments/[model]_[qs_or_o_model]/form.html
  - swcomments/[model]/form.html
  - swcomments/form.html

  There will be a 'form' object made available to the template as well as a 'object' object
  (the original object).
  """
  SYNTAX_EXCEPTION_STR = "%r tag syntax incorrect (requires a 'for [object]', optional 'of [model]' and optional 'using [templatename]')" 

  try:
    d = _parse(token, { 'for': { 'name': 'o_expr' }, 'of': { 'name': 'model', 'default': 'Comment' }, 'using': { 'name': 'templatename' } })
  except:
    raise template.TemplateSyntaxError(SYNTAX_EXCEPTION_STR % (tag_name,))

  return SWCommentsRenderFormNode(**d)

@register.filter
def swcomments_thread(arg):
  """Filter to be used in a for loop/with statement that threads the comment list/queryset.
  Uses the actual comment class' "thread" method (if available) to do the work"""
  if not isinstance(arg, (QuerySet, tuple, list)): return arg
  l = list(arg)
  if not l: return arg
  cls = type(l[0])
  if not hasattr(cls, 'do_thread') or not callable(cls.do_thread): return arg
  return cls.do_thread(l)



