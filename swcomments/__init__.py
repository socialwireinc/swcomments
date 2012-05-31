from swcomments import models, forms, views, signals

def bind_form_to_model(form_class, model_class):
  form_class.MODEL_CLASS = model_class
  model_class.FORM_CLASS = form_class

def __bind_forms_to_models():
  # Bind each model to a form and vice-versa
  pairs = [
    ('Comment', 'CommentForm'),
    ('AnonComment', 'AnonCommentForm'),
    ('QAComment', 'QACommentForm'),
    ('QuestionComment', 'QuestionCommentForm'),
    ('AnswerComment', 'AnswerCommentForm'),
    ('RatingComment', 'RatingCommentForm'),
    ('StackedComment', 'StackedCommentForm'),
    ('StackedRatingComment', 'StackedRatingCommentForm'),
  ]

  for m,f in pairs:
    mc = getattr(models, m, None)
    fc = getattr(forms, f, None)
    if mc and fc:
      bind_form_to_model(fc, mc)

__bind_forms_to_models()

