import django_bootstrap, __main__

if '__file__' in dir(__main__):
  django_bootstrap.bootstrap(__main__.__file__)
else:
  import os
  django_bootstrap.bootstrap(os.getcwd())
