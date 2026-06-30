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
    path('meal-plan/list/', views.meal_plan_list, name='meal_plan_list'),
    path('meal-plan/add/', views.meal_plan_add, name='meal_plan_add'),
    path('meal-plan/<int:entry_id>/edit/', views.meal_plan_edit, name='meal_plan_edit'),
    path('meal-plan/<int:entry_id>/delete/', views.meal_plan_delete, name='meal_plan_delete'),
    path('meal-plan/clear-week/', views.meal_plan_clear_week, name='meal_plan_clear_week'),
    path('ai-scan-ajax/', views.ai_scan_ajax, name='ai_scan_ajax'),
]

handler400 = 'django.views.defaults.bad_request'
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'core.views.custom_404'
handler500 = 'django.views.defaults.server_error'

