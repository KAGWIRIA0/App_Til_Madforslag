from django.urls import path
from . import views
 
urlpatterns = [
    path('', views.home, name='home'),
    path('browse/', views.browse, name='browse'),
    path('about/', views.about, name='about'),
    path('find-dishes/', views.find_dishes, name='find_dishes'),
    path('dish/<int:pk>/', views.dish_detail, name='dish_detail'),
    path('gym/', views.gym, name='gym'),
    path('comrade-kitchen/', views.comrade_kitchen, name='comrade_kitchen'),
    path('comrade-food/<int:pk>/', views.comrade_food_detail, name='comrade_food_detail'),
    path('skin/', views.skin, name='skin'),
    path('ai-scan-ajax/', views.ai_scan_ajax, name='ai_scan_ajax'),
]