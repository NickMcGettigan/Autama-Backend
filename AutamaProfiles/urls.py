from django.urls import path
from . import views as AutamaProfiles_views


app_name = 'AutamaProfiles'

urlpatterns = [
    path('register/', AutamaProfiles_views.register_autama, name='register_autama'),
]