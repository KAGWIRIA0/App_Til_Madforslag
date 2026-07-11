from django.db import models


class Dish(models.Model):
    CATEGORY_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner / Supper'),
        ('anytime', 'Anytime'),
    ]
    BUDGET_CHOICES = [
        ('low', 'Low'),
        ('low-mid', 'Low-Mid'),
        ('mid', 'Mid'),
        ('high', 'High'),
        ('mid-high', 'Mid-High'),
    ]
    MEAL_TYPE_CHOICES = [
        ('food', 'Food'),
        ('drink', 'Drink'),
    ]
    FOOD_ROLE_CHOICES = [
        ('main', 'Main Meal'),
        ('side', 'Side'),
        ('drink', 'Drink'),
        ('snack', 'Snack'),
    ]

    name = models.CharField(max_length=200)
    categories = models.JSONField(default=list, blank=True, help_text="Select one or more: breakfast, lunch, dinner, anytime")
    description = models.TextField()
    ingredients = models.TextField(help_text="Comma-separated list of ingredients")
    estimated_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    prep_time = models.CharField(max_length=50, default="30 mins")
    youtube_url = models.URLField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='dish_images/', blank=True, null=True)
    budget_level = models.CharField(max_length=10, choices=BUDGET_CHOICES, default='low')
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPE_CHOICES, default='food')
    best_with_drinks = models.JSONField(default=list, blank=True)
    best_with_foods = models.JSONField(default=list, blank=True)
    add_ons = models.JSONField(default=list, blank=True)
    is_dry = models.BooleanField(default=False)
    food_role = models.JSONField(default=list)
    recipe_steps = models.TextField(blank=True, null=True, help_text="Write cooking steps, one per line.")

    def get_recipe_steps_list(self):
        if self.recipe_steps:
            return [s.strip() for s in self.recipe_steps.split('\n') if s.strip()]
        return []

    def get_add_ons_list(self):
        return self.add_ons or []

    def get_ingredients_list(self):
        return [i.strip() for i in self.ingredients.split(',')]

    def __str__(self):
        return self.name


class DishStewOption(models.Model):
    STEW_CATEGORY_CHOICES = [
        ('beef', 'Beef'),
        ('chicken', 'Chicken'),
        ('pork', 'Pork'),
        ('fish', 'Fish'),
        ('greens', 'Greens / Vegetables'),
        ('legumes', 'Legumes / Beans'),
        ('egg', 'Egg'),
        ('other', 'Other'),
    ]
    BUDGET_CHOICES = [
        ('low', 'Low'),
        ('low-mid', 'Low-Mid'),
        ('mid', 'Mid'),
        ('high', 'High'),
        ('mid-high', 'Mid-High'),
    ]

    dish = models.ForeignKey(
        'Dish',
        on_delete=models.CASCADE,
        related_name='stew_options'
    )
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=STEW_CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    budget_level = models.CharField(max_length=10, choices=BUDGET_CHOICES, default='low')
    image = models.ImageField(upload_to='stew_options/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    youtube_url = models.URLField(blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    is_vegetarian = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    ingredients = models.TextField(blank=True, help_text="Comma-separated list of ingredients")
    add_ons = models.JSONField(default=list, blank=True)
    recipe_steps = models.TextField(blank=True, null=True, help_text="One step per line")

    def get_ingredients_list(self):
        return [i.strip() for i in self.ingredients.split(',') if i.strip()]

    def get_recipe_steps_list(self):
        if self.recipe_steps:
            return [s.strip() for s in self.recipe_steps.split('\n') if s.strip()]
        return []

    def get_add_ons_list(self):
        return self.add_ons or []

    class Meta:
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return f"{self.name} (goes with {self.dish.name})"


class GymFood(models.Model):
    CATEGORY_CHOICES = [
        ('high-protein', 'High Protein'),
        ('complex-carbs', 'Complex Carbs'),
        ('fruits', 'Fruits'),
        ('hydration', 'Hydration'),
        ('healthy-fats', 'Healthy Fats'),
        ('low-calorie', 'Low Calorie'),
        ('gym-snacks', 'Gym Snacks'),
        ('soup', 'Soup'),
        ('smoothies', 'Smoothie'),
    ]
    PURPOSE_CHOICES = [
        ('weight-loss', 'Ideal for Weight Loss'),
        ('weight-gain', 'Ideal for Weight Gain'),
        ('muscle-build', 'Builds Muscle'),
        ('endurance', 'Boosts Endurance'),
        ('recovery', 'Aids Recovery'),
        ('general', 'General Fitness'),
    ]
    TYPE_CHOICES = [
        ('food', 'Food'),
        ('drink', 'Drink'),
        ('snack', 'Snack'),
    ]
    TIMING_CHOICES = [
        ('pre-workout', 'Pre-Workout'),
        ('during-workout', 'During Workout'),
        ('post-workout', 'Post-Workout'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    food_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='food')
    timing = models.CharField(max_length=20, choices=TIMING_CHOICES, default='pre-workout')
    timing_detail = models.CharField(max_length=100, blank=True)
    benefits = models.TextField(help_text="One benefit per line")
    ingredients = models.TextField(blank=True, help_text="Comma-separated list of ingredients")
    protein = models.IntegerField(default=0)
    carbs = models.IntegerField(default=0)
    fats = models.IntegerField(default=0)
    image = models.ImageField(upload_to='gym_foods/', blank=True, null=True)
    recipe_steps = models.TextField(blank=True, null=True, help_text="One step per line")
    youtube_url = models.URLField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    purpose = models.CharField(max_length=50, choices=PURPOSE_CHOICES, default='general', help_text="What is this food ideal for?")

    def get_benefits_list(self):
        return [b.strip() for b in self.benefits.split('\n') if b.strip()]

    def __str__(self):
        return self.name
    def get_ingredients_list(self):
        return [i.strip() for i in self.ingredients.split(',') if i.strip()]

    def get_recipe_steps(self):
        return [s.strip() for s in self.recipe_steps.split('\n') if s.strip()]

class ComradeFood(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='comrade_foods/', blank=True, null=True)
    description = models.TextField()
    price_ksh = models.IntegerField(help_text="Price in Kenyan Shillings")
    unit = models.CharField(max_length=100, help_text="e.g. per packet, per kg, per piece")
    youtube_url = models.URLField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    cooking_tip = models.TextField(
        blank=True,
        help_text="Budget cooking tip e.g. 'Boil with salt for fastest meal'"
    )

    def __str__(self):
        return f"{self.name} — Ksh {self.price_ksh}"



class ComradeMeal(models.Model):
    CATEGORY_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner / Supper'),
        ('anytime', 'Anytime'),
    ]
    MEAL_TYPE_CHOICES = [
        ('food', 'Food'),
        ('drink', 'Drink'),
        ('snack', 'Snack'),
    ]
    name = models.CharField(max_length=200)
    categories = models.JSONField(default=list, blank=True, help_text="Select one or more: breakfast, lunch, dinner, anytime")
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPE_CHOICES, default='food')
    description = models.TextField()
    total_cost_ksh = models.IntegerField()
    items = models.JSONField(
        help_text='List of {"item": "Indomie", "cost": 45, "qty": "1 packet"}'
    )
    kitchen_items_needed = models.TextField(
        help_text="Comma-separated items from kitchen e.g. cooking oil, salt",
        blank=True
    )
    steps = models.TextField(
        help_text="One cooking step per line",
        blank=True
    )
    upgrade_with = models.TextField(
        help_text="e.g. Add onions+tomatoes if you have them",
        blank=True
    )
    cooking_tip = models.TextField(
        blank=True,
        help_text="Quick cooking tip e.g. 'Boil with salt for fastest meal'"
    )
    youtube_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='comrade_meals/', blank=True, null=True)
    tags = models.CharField(
        max_length=200,
        blank=True,
        help_text="Comma-separated tags e.g. fastest,vegetarian,filling"
    )
    comrade_food = models.ForeignKey(
        'ComradeFood',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meals',
        help_text="Link to the base ComradeFood item (e.g. Rice) to show Eat With stew options"
    )

    def get_steps_list(self):
        return [s.strip() for s in self.steps.split('\n') if s.strip()]

    def get_kitchen_items(self):
        return [k.strip() for k in self.kitchen_items_needed.split(',') if k.strip()]

    def get_tags(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def get_items(self):
        return self.items or []

    def __str__(self):
        return f"{self.name} — Ksh {self.total_cost_ksh}"
    
class ComradeMealStewOption(models.Model):
    STEW_CATEGORY_CHOICES = [
        ('beef', 'Beef'),
        ('chicken', 'Chicken'),
        ('pork', 'Pork'),
        ('fish', 'Fish'),
        ('greens', 'Greens / Vegetables'),
        ('legumes', 'Legumes / Beans'),
        ('egg', 'Egg'),
        ('other', 'Other'),
    ]
    BUDGET_CHOICES = [
        ('low', 'Low'),
        ('low-mid', 'Low-Mid'),
        ('mid', 'Mid'),
        ('high', 'High'),
        ('mid-high', 'Mid-High'),
    ]

    comrade_meal = models.ForeignKey(
        'ComradeMeal',
        on_delete=models.CASCADE,
        related_name='stew_options'
    )
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=STEW_CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    budget_level = models.CharField(max_length=10, choices=BUDGET_CHOICES, default='low')
    image = models.ImageField(upload_to='stew_options/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    youtube_url = models.URLField(blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    is_vegetarian = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    ingredients = models.TextField(blank=True, help_text="Comma-separated list of ingredients")
    add_ons = models.JSONField(default=list, blank=True)
    recipe_steps = models.TextField(blank=True, null=True, help_text="One step per line")

    def get_ingredients_list(self):
        return [i.strip() for i in self.ingredients.split(',') if i.strip()]

    def get_recipe_steps_list(self):
        if self.recipe_steps:
            return [s.strip() for s in self.recipe_steps.split('\n') if s.strip()]
        return []

    def get_add_ons_list(self):
        return self.add_ons or []

    class Meta:
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return f"{self.name} (goes with {self.comrade_meal.name})"    
    
class SkinFood(models.Model):
    CATEGORY_CHOICES = [
        ('glow', 'Natural Glow'),
        ('hydration', 'Deep Hydration'),
        ('clearer', 'Clearer Skin'),
        ('aging', 'Anti-Aging'),
        ('firm', 'Firm & Elastic'),
        ('detox', 'Detox & Purify'),
        ('brightening', 'Brightening'),
        ('sensitive', 'Sensitive Skin'),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    benefit_summary = models.CharField(max_length=200,
        help_text="Short one-liner e.g. 'Reduces redness & boosts glow'")
    description = models.TextField(
        help_text="Full benefit description shown on the card")
    key_nutrient = models.CharField(max_length=100,
        help_text="e.g. Beta-Carotene, Vitamin C, Omega-3")
    how_to_use = models.TextField(blank=True,
        help_text="How to incorporate this food e.g. 'Add to smoothies daily'")
    image = models.ImageField(upload_to='skin_foods/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0,
        help_text="Display order within category (lower = first)")

    class Meta:
        ordering = ['category', 'order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"    
    
class WellnessFood(models.Model):
    CATEGORY_CHOICES = [
        ('immunity', 'Immunity'),
        ('energy', 'Energy & Vitality'),
        ('gut', 'Gut Health'),
        ('sleep', 'Better Sleep'),
        ('stress', 'Stress Relief'),
        ('brain', 'Brain & Focus'),
        ('weight', 'Weight Balance'),
        ('hormones', 'Hormonal Balance'),
    ]
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    benefit_summary = models.CharField(max_length=200)
    description = models.TextField()
    key_nutrient = models.CharField(max_length=100)
    how_to_use = models.TextField(blank=True)
    image = models.ImageField(upload_to='wellness_foods/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['category', 'order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    

class MealPlanEntry(models.Model):
    session_key = models.CharField(max_length=40, db_index=True)
    date = models.CharField(max_length=10)   # ISO format e.g. "2026-06-30"
    slot = models.CharField(max_length=10)   # breakfast / lunch / dinner
    name = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'slot', 'created_at']

    def __str__(self):
        return f"{self.name} — {self.date} {self.slot}"