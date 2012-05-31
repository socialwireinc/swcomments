import time

from django.conf import settings
from django import forms
from django.utils.hashcompat import sha_constructor
from django.contrib.contenttypes.models import ContentType
from django.core import exceptions

from swcomments import models

COMMENT_MAX_LENGTH = 5000
COMMENT_TIMEOUT = 3*60*60

join_strs = "".join

class BaseCommentForm(forms.Form):
  """
  Basic swcomments.Comment form.
  Security items taken from stock django comment system.
  """

  MODEL_CLASS = None

  comment_model = forms.CharField(widget=forms.HiddenInput)
  content_type = forms.CharField(widget=forms.HiddenInput)
  object_pk = forms.CharField(widget=forms.HiddenInput)
  timestamp = forms.IntegerField(widget=forms.HiddenInput)
  security_hash = forms.CharField(min_length=40, max_length=40, widget=forms.HiddenInput)
  tn = forms.CharField(required=False, max_length=255, widget=forms.HiddenInput)

  title = forms.CharField(help_text="Comment Title", max_length=255, required=False)
  comment = forms.CharField(help_text='Comment (up to %d characters)' % (COMMENT_MAX_LENGTH,), 
                            widget=forms.Textarea, max_length=COMMENT_MAX_LENGTH)

  def __init__(self, target_object, data=None, initial=None, template_name=None):
    self.target_object = target_object
    if initial is None:
      initial = {}
    initial.update(self.generate_security_data())
    self.template_name = template_name
    if self.template_name: initial['tn'] = self.encode_template_name()
    super(BaseCommentForm, self).__init__(data=data, initial=initial)

  @classmethod
  def get_model_class(cls):
    """Returns the model class associated with this form"""
    if cls.MODEL_CLASS:
      return cls.MODEL_CLASS
    raise NotImplementedError("No model has been bound to form class '%s'" % (cls.__name__,))

  def encode_template_name(self):
    # Encodes self.template_name
    data = join_strs((self.template_name or '',  settings.SECRET_KEY))
    return ("%s,%s" % (self.template_name, sha_constructor(data).hexdigest())).encode('base64')

  @classmethod
  def decode_template_name(cls, tn):
    name,hash = tn.decode('base64').split(",")
    data = join_strs((name,  settings.SECRET_KEY))
    if hash == sha_constructor(data).hexdigest():
      return name
    return None

  def clean_security_hash(self):
    """Check the security hash."""
    security_hash_dict = {
      'comment_model' : self.data.get("comment_model", ""),
      'content_type' : self.data.get("content_type", ""),
      'object_pk' : self.data.get("object_pk", ""),
      'timestamp' : self.data.get("timestamp", ""),
    }
    expected_hash = self.generate_security_hash(**security_hash_dict)
    actual_hash = self.cleaned_data["security_hash"]
    if expected_hash != actual_hash:
      raise forms.ValidationError("Security hash check failed.")
    return actual_hash

  def clean_timestamp(self):
    """Make sure the timestamp isn't too far (> X hours) in the past."""
    ts = self.cleaned_data["timestamp"]
    if time.time() - ts > COMMENT_TIMEOUT:
      raise forms.ValidationError("Comment timeout - please reload page and try again")
    return ts

  '''
  def additional_security_data(self, initial=False):
    """Subclasses can add data to the hash via this method.  If 'initial' is True, then
    we want the initial value of the form (not the POSTed result).
    This method can use actual non-generated fields, which could come in handy for 
    tamper detection of hidden fields."""
    return {}
  '''

  def generate_security_data(self):
    """Generate a dict of security data for "initial" data."""
    timestamp = int(time.time())
    security_dict =   {
      'comment_model'  : str(self.get_model_class()._meta),
      'content_type'  : str(self.target_object._meta),
      'object_pk'     : str(self.target_object._get_pk_val()),
      'timestamp'     : str(timestamp),
      'security_hash' : self.initial_security_hash(timestamp),
    }
    return security_dict

  def initial_security_hash(self, timestamp):
    """
    Generate the initial security hash from self.content_object
    and a (unix) timestamp.
    """

    initial_security_dict = {
      'comment_model'  : str(self.get_model_class()._meta),
      'content_type' : str(self.target_object._meta),
      'object_pk' : str(self.target_object._get_pk_val()),
      'timestamp' : str(timestamp),
    }
    #initial_security_dict.update(self.additional_security_data(initial=True))
    return self.generate_security_hash(**initial_security_dict)

  def generate_security_hash(self, comment_model, content_type, object_pk, timestamp):
    """Generate a (SHA1) security hash from the provided info."""
    info = (content_type, object_pk, timestamp, settings.SECRET_KEY)
    return sha_constructor("".join(info)).hexdigest()

  def clean_content_type(self):
    ct = self.cleaned_data['content_type']
    #raise exceptions.SuspiciousOperation("Field 'content_type' is unknown")
    return ct

  def get_model_data(self):
    """Method creates the model data that will be used to save the comment to the database.  It
    returns a dictionary containing the data (suitable to pass to the comment model constructor).
    Subclasses can override this method and add to the dictionary."""
    # Leaving status, site, user, submit_date out as they're not necessary...
    return dict(
      content_type = ContentType.objects.get_by_natural_key(*self.cleaned_data['content_type'].split(".", 1)),
      object_pk = self.cleaned_data['object_pk'],
      comment = self.cleaned_data['comment'],
    )

class CommentForm(BaseCommentForm):
  """Comment Form"""

class AnonCommentForm(BaseCommentForm):
  """Extra fields from the Anonymous Comment model"""

  name = forms.CharField(help_text="Your Name", max_length=50)
  email = forms.EmailField(help_text="Your email address (won't be shown anywhere)")
  url = forms.URLField(help_text="Your website", required=False)

  def get_model_data(self):
    data = super(AnonCommentForm, self).get_model_data()
    data.update(dict(
      name = self.cleaned_data['name'],
      email = self.cleaned_data['email'],
      url = self.cleaned_data['url'],
    ))
    return data

class QACommentForm(BaseCommentForm):
  "question/answer comment form"""

  comment_type = forms.IntegerField(widget=forms.HiddenInput) #, initial=models.QAComment.COMMENTTYPE_QUESTION)
  question_id = forms.IntegerField(widget=forms.HiddenInput, required=False)

  '''
  def additional_security_data(self, initial=False):
    if initial:
      return {
        'comment_type' : str(self.initial.get('comment_type', self.comment_type.initial))
      }
    return {
      'comment_type' : str(self.data('comment_type', ''))
    }
  '''  

  def get_model_data(self):
    data = super(QACommentForm, self).get_model_data()
    data.update(dict(
      comment_type = self.cleaned_data['comment_type'],
      question_id = self.cleaned_data['question_id'],
    ))
    return data

class QuestionCommentForm(QACommentForm):
  """question"""

  def __init__(self, *args, **kwargs):
    if 'initial' not in kwargs or kwargs['initial'] is None:
      kwargs['initial'] = {}
    kwargs['initial']['comment_type'] = models.QAComment.COMMENTTYPE_QUESTION
    super(QuestionCommentForm, self).__init__(*args, **kwargs)

class AnswerCommentForm(QACommentForm):
  """answer"""

  def __init__(self, *args, **kwargs):
    if 'initial' not in kwargs or kwargs['initial'] is None:
      kwargs['initial'] = {}
    if 'question' in kwargs:
      kwargs['initial']['question_id'] = kwargs['question'].id
      del kwargs['question']
    kwargs['initial']['comment_type'] = models.QAComment.COMMENTTYPE_ANSWER
    super(AnswerCommentForm, self).__init__(*args, **kwargs)

class BaseStackedCommentForm(forms.Form):
  """Base for a StackedComment form -- nothing to do here."""

class StackedCommentForm(BaseStackedCommentForm, BaseCommentForm):
  """StackedComment Form"""

class BaseRatingCommentForm(forms.Form):
  """Base for a RatingComment form (contains a 'score' hidden field')"""

  score = forms.IntegerField(widget=forms.HiddenInput, validators=[models.rating_vmin, models.rating_vmax])

  def get_model_data(self):
    data = super(BaseRatingCommentForm, self).get_model_data()
    data.update(dict(
      score = self.cleaned_data['score'],
    ))
    return data

class RatingCommentForm(BaseRatingCommentForm, BaseCommentForm):
  """RatingComment Form"""

class StackedRatingCommentForm(BaseStackedCommentForm, BaseRatingCommentForm, BaseCommentForm):
  """StackedRatingComment Form"""


