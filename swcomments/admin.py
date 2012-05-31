from django.contrib import admin
from swcomments import models

class CommentAdmin(admin.ModelAdmin):
  list_display = [ "id", "status", "submit_date", "title", "user", "content_type" ]

class QACommentAdmin(admin.ModelAdmin):
  list_display = [ "id", "status", "submit_date", "title", "user", "content_type", "comment_type", "question" ]

class RatingCommentAdmin(admin.ModelAdmin):
  list_display = [ "id", "status", "submit_date", "title", "user", "content_type" ]

class StackedCommentAdmin(admin.ModelAdmin):
  list_display = [ "id", "status", "submit_date", "title", "user", "content_type" ]

class StackedRatingCommentAdmin(admin.ModelAdmin):
  list_display = [ "id", "status", "submit_date", "title", "user", "content_type" ]

admin.site.register(models.Comment, CommentAdmin)
admin.site.register(models.QAComment, QACommentAdmin)
admin.site.register(models.StackedComment, StackedCommentAdmin)
if hasattr(models, 'RatingComment'): admin.site.register(models.RatingComment, RatingCommentAdmin)
if hasattr(models, 'RatingComment'): admin.site.register(models.StackedRatingComment, StackedRatingCommentAdmin)

