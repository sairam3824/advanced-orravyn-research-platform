from django.urls import path
from . import views

app_name = 'ml_engine'

urlpatterns = [
    path('generate/', views.generate_recommendations_for_user, name='generate_recommendations'),
    path('my/', views.user_recommendations, name='user_recommendations'),
]
