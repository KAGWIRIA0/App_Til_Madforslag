from django.contrib import admin
from .models import Dish, DishStewOption, ComradeMealStewOption, GymFood, ComradeFood, ComradeMeal, SkinFood, WellnessFood


class DishStewOptionInline(admin.TabularInline):
    model = DishStewOption
    extra = 3
    fields = ['name', 'category', 'description', 'budget_level', 'image', 'image_url', 'youtube_url',
              'estimated_cost', 'is_vegetarian', 'is_featured', 'ingredients', 'add_ons', 'recipe_steps']


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    inlines = [DishStewOptionInline]
    list_display = ['name', 'category', 'estimated_cost', 'prep_time']
    list_filter = ['category']
    search_fields = ['name', 'ingredients']


@admin.register(DishStewOption)
class DishStewOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'dish', 'category', 'estimated_cost', 'is_featured']
    list_filter = ['category', 'is_vegetarian', 'is_featured']
    search_fields = ['name']


@admin.register(GymFood)
class GymFoodAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'food_type', 'timing', 'protein', 'carbs', 'fats']
    list_filter = ['category', 'food_type', 'timing']
    search_fields = ['name', 'description']

class ComradeMealStewOptionInline(admin.TabularInline):
    model = ComradeMealStewOption
    extra = 3
    fields = ['name', 'category', 'description', 'budget_level', 'image', 'image_url', 'youtube_url',
              'estimated_cost', 'is_vegetarian', 'is_featured', 'ingredients', 'add_ons', 'recipe_steps']


@admin.register(ComradeFood)
class ComradeFoodAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price_ksh', 'unit']
    list_filter = ['category']
    search_fields = ['name']


@admin.register(ComradeMealStewOption)
class ComradeMealStewOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'comrade_meal', 'category', 'estimated_cost', 'is_featured']
    list_filter = ['category', 'is_vegetarian', 'is_featured']
    search_fields = ['name']


@admin.register(ComradeMeal)
class ComradeMealAdmin(admin.ModelAdmin):
    inlines = [ComradeMealStewOptionInline]
    list_display = ['name', 'total_cost_ksh']
    search_fields = ['name']

@admin.register(SkinFood)
class SkinFoodAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'key_nutrient', 'is_featured', 'order']
    list_filter   = ['category', 'is_featured']
    list_editable = ['order', 'is_featured']
    search_fields = ['name', 'key_nutrient']
    ordering      = ['category', 'order']    

@admin.register(WellnessFood)
class WellnessFoodAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'key_nutrient', 'is_featured', 'order']
    list_filter   = ['category', 'is_featured']
    list_editable = ['order', 'is_featured']
    search_fields = ['name', 'key_nutrient']