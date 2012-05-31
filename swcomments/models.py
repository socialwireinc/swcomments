"""
swcomments

Defines comment models that we can use.  
"""

import datetime

from django.db import models
from django.db.models.query import QuerySet
from django.core import validators
from django.contrib.auth import models as authmodels
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.sites.models import Site

import settings

class BaseCommentManager(models.Manager):
  """
  Manager for all Comment models.
  Takes care of including comments for correct site.
  Also makes available a active() method which returns only active comments.
  """
  def __init__(self, activeonly=False):
    self.__activeonly=activeonly
    super(BaseCommentManager, self).__init__()
  def get_query_set(self):
    qs = super(BaseCommentManager, self).get_query_set() \
        .filter(site=settings.SITE_ID) \
        .select_related('user')
    if self.__activeonly:
      qs = qs.filter(status=BaseComment.STATUS_ACTIVE)
    return qs

class BaseComment(models.Model):
  """
  A very basic comment with the bare essentials.
  You should not actually use this model, it is meant to subclass.
  """

  FORM_CLASS = None    # Sub-classes should override this

  STATUS_ACTIVE = 1
  STATUS_DELETED = -1

  STATUSES = (
    (STATUS_ACTIVE, "Active"),
    (STATUS_DELETED, "Deleted"),
  )

  ORDER = {
    'asc' : 'submit_date',
    'desc' : '-submit_date',
  }

  status         = models.IntegerField(choices=STATUSES, default=STATUS_ACTIVE)

  user           = models.ForeignKey(authmodels.User, related_name="%(app_label)s_%(class)s_set")
  ip_address     = models.IPAddressField(blank=True, null=True, default="0.0.0.0")   # default cause of SHITTY Django bug

  submit_date    = models.DateTimeField(auto_now_add=True)
  title          = models.CharField(max_length=255, blank=True, null=True)
  comment        = models.TextField()

  site           = models.ForeignKey(Site, related_name="%(app_label)s_%(class)s_set")

  content_type   = models.ForeignKey(ContentType, related_name="content_type_set_for_%(app_label)s_%(class)s")
  object_pk      = models.TextField()
  content_object = GenericForeignKey(ct_field="content_type", fk_field="object_pk")

  objects = BaseCommentManager()
  active = BaseCommentManager(True)

  def save(self, *args, **kwargs):
    # If we did not specify a site, use current site
    if self.site_id is None:
      self.site = Site.objects.get_current()
    super(BaseComment, self).save(*args, **kwargs)

  @classmethod
  def do_thread(cls, qs):
    """Sub-classes of BaseComment can implement this to sort data in a "threaded" kind of way."""
    return qs

  @classmethod
  def do_count(cls, qs):
    """Sub-classes of BaseComment can implement this to add on to the queryset..."""
    if not isinstance(qs, QuerySet):
      raise TypeError("Parameter passed to do_count() method must be a QuerySet")
    return qs

  @classmethod
  def get_form_class(cls):
    """Comment models are responsible for telling django what form is associated with them.
    The FORM_CLASS class attribute must be defined for this method to work (but not for 
    the model to be used)"""
    if cls.FORM_CLASS:
      return cls.FORM_CLASS
    raise NotImplementedError("No form has been defined for class '%s'" % (cls.__name__,))

  @classmethod
  def get_nonproxy_model_name(cls):
    """Return the app_label and model name of the first non-proxy comment model that is associated 
    with this model (useful for template loading)"""
    m = cls
    while m._meta.proxy:
      m = m._meta.proxy_for_model
    if not issubclass(m, BaseComment):
      raise TypeError('Model has no non-proxy super class: %s' % (m.__name__,))
    ct = ContentType.objects.get_for_model(m)
    return ct.app_label, ct.model

  class Meta:
    # This model is meant to be inherited
    abstract = True
    ordering = [ '-submit_date' ]

class Comment(BaseComment):
  """Just a basic comment, no frills"""

#
# Anonymous Comment
#

class BaseAnonComment(BaseComment):
  """Same basic comment, but with the "anonymous" user fields (name, etc)"""
  user_name   = models.CharField(max_length=50, blank=True)
  user_email  = models.EmailField(blank=True)
  user_url    = models.URLField(blank=True)

  class Meta:
    # This model is meant to be inherited
    abstract = True

class AnonComment(BaseAnonComment):
  """Actual Anonymous Comment"""

#
# QA Comment
#

class BaseQACommentManager(BaseCommentManager):
  """
  Manager for all QAComment models (and descendants).
  Takes care of including comments for correct site.
  Also makes available a active() method which returns only active comments.
  """
  def __init__(self, activeonly=False, whichtype=None, unansweredonly=False):
    self.__whichtype = whichtype
    self.__unansweredonly = unansweredonly
    super(BaseQACommentManager, self).__init__(activeonly)
  def get_query_set(self):
    qs = super(BaseQACommentManager, self).get_query_set()
    if self.__whichtype is not None: qs = qs.filter(comment_type=self.__whichtype)
    if self.__unansweredonly: qs = qs.annotate(num_answers=models.Count('answers')).filter(num_answers=0)
    return qs
  #def questions(self):
  #  return self.active().get_query_set().filter(comment_type=BaseQAComment.COMMENTTYPE_QUESTION)
  #def answers(self):
  #  return self.active().filter(comment_type=BaseQAComment.COMMENTTYPE_ANSWER)

class BaseQAComment(BaseAnonComment):
  """Question/Answer comment, not threaded, just tracks if a parent exists
  (ie. it was answered).  Any further question/answer inherits existing parent."""
 
  COMMENTTYPE_QUESTION = 0
  COMMENTTYPE_ANSWER = 1
  COMMENTTYPES = (
    ( COMMENTTYPE_QUESTION, 'Question' ),
    ( COMMENTTYPE_ANSWER, 'Answer' ),
  )

  comment_type = models.IntegerField(choices=COMMENTTYPES, default=COMMENTTYPE_QUESTION)
  question = models.ForeignKey("QAComment", related_name="answers", blank=True, null=True)

  objects = BaseQACommentManager()
  active = BaseQACommentManager(activeonly=True)

  def is_answered(self):
    return self.answers.count() > 0

  def is_question(self):
    return self.comment_type == self.COMMENTTYPE_QUESTION

  def is_answer(self):
    return self.comment_type == self.COMMENTTYPE_ANSWER

  def __unicode__(self):
    return 'QAComment: %s (id# %s)' % (self.title or '-no title-', self.id)

  @classmethod
  def do_thread(cls, qs):
    """Given a queryset (or any sequence, really) of QAComment objects, "thread" it (ie.
    sort them by question and answer per question) and return a sequence."""
    qs = super(BaseQAComment, cls).do_thread(qs)
    cl = list(qs)
    ql = [ c for c in cl if c.is_question() ]
    ad = {}
    for a in [ c for c in cl if c.is_answer() ]:
      if a.question not in ad:
        ad[a.question] = [a]
      else:
        ad[a.question].append(a)
    tl = []
    for q in ql:
      tl.append(q)
      if q in ad: tl.extend(ad[q])
    return tl

  class Meta:
    # This model is meant to be inherited
    abstract = True
    ordering = [ 'submit_date' ]

class QAComment(BaseQAComment):
  """Actual QA Comment Model"""

class QuestionComment(QAComment):
  """
  Proxy model that automatically sets type to 'Question'.  
  Default manager (objects) filters only questions.  A 2nd manager (unanswered) only returns questions
  that have no answers.  In both cases, only active questions are returned."""
  objects = BaseQACommentManager(activeonly=True, whichtype=QAComment.COMMENTTYPE_QUESTION)
  unanswered = BaseQACommentManager(activeonly=True, whichtype=QAComment.COMMENTTYPE_QUESTION, unansweredonly=True)

  def save(self, *args, **kwargs):
    self.comment_type = self.COMMENTTYPE_QUESTION
    super(QAComment, self).save(*args, **kwargs)

  class Meta:
    # This model is just a proxy over QAComment
    proxy = True

class AnswerComment(QAComment):
  """
  Proxy model that automatically sets type to 'Answer'.
  Default manager (objects) filters only answers.  Only active answers are returned.
  """

  objects = BaseQACommentManager(activeonly=True, whichtype=QAComment.COMMENTTYPE_ANSWER)

  def save(self, *args, **kwargs):
    self.comment_type = self.COMMENTTYPE_ANSWER
    super(QAComment, self).save(*args, **kwargs)

  class Meta:
    # This model is just a proxy over QAComment
    proxy = True

#
# StackedComment
#

class BaseStackedComment(models.Model):
  """
  A stacked comment is where a user's multiple comments will 'stack' together.
  Its not really meant as a "conversation" style, as you can't reply to someone else.
  It uses a 'stackdate' variable to allow retrieving of comments by 'stack' (sorted 
  by 'stackdate' rather than by date).
  """

  stack_date = models.DateTimeField(auto_now_add=True)

  def save(self, *args, **kwargs):
    is_insert = not self.id
    super(BaseStackedComment, self).save(*args, **kwargs)
    # On insert, update all comments in this "stack" (ie user/content_object) to have same stack_date
    if is_insert:
      self.__class__.objects  \
          .filter(user=self.user, content_type=self.content_type, object_pk=self.object_pk)  \
          .update(stack_date=self.submit_date)

  def is_top(self):
    return self.stack_date is not None and self.stack_date == self.submit_date

  @classmethod
  def do_count(cls, qs):
    """
    The "number" of comments is actually the number of tops (ie. where stack_date = submit_date).
    Logically there should be exactly one stack per user per content_object...
    """
    qs = super(BaseStackedComment, cls).do_count(qs)
    qs = qs.extra(where=['stack_date = submit_date'])
    return qs

  @classmethod
  def do_thread(cls, qs):
    """
    """
    comments = list(qs)
    count = len(comments)
    idx = 0
    while idx < count:
      top = comments[idx]
      top.others = []
      idx += 1
      while idx < count:
        c = comments[idx]
        if c.user != top.user:
          break
        top.others.append(c)
        idx += 1
      yield top

  class Meta:
    # This model is meant to be inherited
    abstract = True
    ordering = [ '-stack_date', 'user', '-submit_date' ]

class StackedComment(BaseStackedComment, BaseComment):
  """Actual Stacked Comment Model"""

#
# Rated Comment
#

if 'djangoratings' in settings.INSTALLED_APPS:
  # Make rating field available
  from djangoratings.fields import RatingField

  # The range of the rating (0-?) for the RatingComment
  RATING_RANGE = getattr(settings, 'SWCOMMENTS_RATING_RANGE', 100)
  if not isinstance(RATING_RANGE, int) or RATING_RANGE < 1:
    raise TypeError('settings.SWCOMMENTS_RATING_RANGE must be a positive integer')

  rating_vmin = validators.MinValueValidator(0)
  rating_vmax = validators.MaxValueValidator(RATING_RANGE)

  class BaseRatingComment(models.Model):
    """
    Basic comment + Rating field.
    This Comment allows a user to rate the object in addition to commenting on it (score, 0-RATING_RANGE).
    It also allows others to rate the comment/rating itself (rated, 0/1).
    Just don't use whichever one you don't want to use.
    """
    score = models.IntegerField("Rating/Score",   # Rating(score) given to object that is being commented on.
                validators=[rating_vmin, rating_vmax])
    rated = RatingField(range=2)                  # Rating on the comment itself.

    class Meta:
      # This model is meant to be inherited
      abstract = True

  class RatingComment(BaseRatingComment, BaseComment):
    """Actual RatingComment Model"""

  class StackedRatingComment(BaseStackedComment, BaseRatingComment, BaseComment):
    """Mix of Stacked and RatingComment models, for extra fun"""

    class Meta(BaseStackedComment.Meta):
      pass

#
# Threaded Comment
# 

if 'treebeard' in settings.INSTALLED_APPS:
  pass

