from django import forms
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import (
    Dish, DishStewOption, ComradeMealStewOption,
    GymFood, ComradeFood, ComradeMeal, SkinFood, WellnessFood, MealPlanEntry
)

MEAL_CATEGORY_CHOICES = [
    ('breakfast', 'Breakfast'),
    ('lunch', 'Lunch'),
    ('dinner', 'Dinner / Supper'),
    ('anytime', 'Anytime'),
]


class CategoryMultipleChoiceField(forms.MultipleChoiceField):
    """Renders as checkboxes, saves as a JSON list."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('choices', MEAL_CATEGORY_CHOICES)
        kwargs.setdefault('widget', forms.CheckboxSelectMultiple)
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)


class DishAdminForm(forms.ModelForm):
    categories = CategoryMultipleChoiceField()

    class Meta:
        model = Dish
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['categories'].initial = self.instance.categories or []


class ComradeMealAdminForm(forms.ModelForm):
    categories = CategoryMultipleChoiceField()

    class Meta:
        model = ComradeMeal
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['categories'].initial = self.instance.categories or []


class DishStewOptionInline(admin.TabularInline):
    model = DishStewOption
    extra = 3
    fields = [
        'name', 'category', 'description', 'budget_level',
        'image', 'image_url', 'youtube_url', 'estimated_cost',
        'is_vegetarian', 'is_featured', 'ingredients', 'add_ons', 'recipe_steps'
    ]


@admin.register(Dish)
class DishAdmin(ImportExportModelAdmin):
    form = DishAdminForm
    inlines = [DishStewOptionInline]
    list_display = ['name', 'get_categories', 'estimated_cost', 'prep_time']
    list_filter = ['budget_level', 'meal_type']
    search_fields = ['name', 'ingredients']

    def get_categories(self, obj):
        return ", ".join(obj.categories or [])
    get_categories.short_description = 'Categories'


@admin.register(DishStewOption)
class DishStewOptionAdmin(ImportExportModelAdmin):
    list_display = ['name', 'dish', 'category', 'estimated_cost', 'is_featured']
    list_filter = ['category', 'is_vegetarian', 'is_featured']
    search_fields = ['name']


@admin.register(GymFood)
class GymFoodAdmin(ImportExportModelAdmin):
    list_display = ['name', 'category', 'food_type', 'timing', 'protein', 'carbs', 'fats']
    list_filter = ['category', 'food_type', 'timing']
    search_fields = ['name', 'description']


class ComradeMealStewOptionInline(admin.TabularInline):
    model = ComradeMealStewOption
    extra = 3
    fields = [
        'name', 'category', 'description', 'budget_level',
        'image', 'image_url', 'youtube_url', 'estimated_cost',
        'is_vegetarian', 'is_featured', 'ingredients', 'add_ons', 'recipe_steps'
    ]


@admin.register(ComradeFood)
class ComradeFoodAdmin(ImportExportModelAdmin):
    list_display = ['name', 'price_ksh', 'unit']
    search_fields = ['name']


@admin.register(ComradeMealStewOption)
class ComradeMealStewOptionAdmin(ImportExportModelAdmin):
    list_display = ['name', 'comrade_meal', 'category', 'estimated_cost', 'is_featured']
    list_filter = ['category', 'is_vegetarian', 'is_featured']
    search_fields = ['name']


@admin.register(ComradeMeal)
class ComradeMealAdmin(ImportExportModelAdmin):
    form = ComradeMealAdminForm
    inlines = [ComradeMealStewOptionInline]
    list_display = ['name', 'get_categories', 'total_cost_ksh']
    list_filter = ['meal_type']
    search_fields = ['name']

    def get_categories(self, obj):
        return ", ".join(obj.categories or [])
    get_categories.short_description = 'Categories'


@admin.register(SkinFood)
class SkinFoodAdmin(ImportExportModelAdmin):
    list_display = ['name', 'category', 'key_nutrient', 'is_featured', 'order']
    list_filter = ['category', 'is_featured']
    list_editable = ['order', 'is_featured']
    search_fields = ['name', 'key_nutrient']
    ordering = ['category', 'order']


@admin.register(WellnessFood)
class WellnessFoodAdmin(ImportExportModelAdmin):
    list_display = ['name', 'category', 'key_nutrient', 'is_featured', 'order']
    list_filter = ['category', 'is_featured']
    list_editable = ['order', 'is_featured']
    search_fields = ['name', 'key_nutrient']

@admin.register(MealPlanEntry)
class MealPlanEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'slot', 'session_key', 'created_at')
    list_filter = ('slot', 'date')
    search_fields = ('name', 'session_key')
    ordering = ('-created_at',)    