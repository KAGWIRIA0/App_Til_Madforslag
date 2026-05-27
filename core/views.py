from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Dish, GymFood, ComradeFood, ComradeMeal, SkinFood, WellnessFood
from .ai_engine import suggest_meals_from_ingredients, suggest_from_voice, suggest_meals_from_image
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import random


def home(request):
    def get_meal(category):
        mains  = list(Dish.objects.filter(category=category, food_role__icontains="main"))
        drinks = list(Dish.objects.filter(category=category, food_role__icontains="drink"))
        sides  = list(Dish.objects.filter(category=category, food_role__icontains="side"))
        return {
            "main":  random.choice(mains)  if mains  else None,
            "drink": random.choice(drinks) if drinks else None,
            "side":  random.choice(sides)  if sides  else None,
        }

    return render(request, 'core/home.html', {
        'breakfast': get_meal('breakfast'),
        'lunch':     get_meal('lunch'),
        'dinner':    get_meal('dinner'),
        'anytime':   get_meal('anytime'),
    })


def browse(request):
    category = request.GET.get('category', '')
    role = request.GET.get('role', '')
    search_query = request.GET.get('q', '')

    dishes = Dish.objects.all()

    if category:
        dishes = dishes.filter(category=category)

    if role:
        dishes = dishes.filter(food_role__icontains=role)

    if search_query:
        dishes = dishes.filter(
            Q(name__icontains=search_query) |
            Q(ingredients__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Split into foods and drinks 
    foods = dishes.filter(meal_type='food')
    drinks = dishes.filter(meal_type='drink')

    # Paginate foods
    food_paginator = Paginator(foods, 6)
    food_page = request.GET.get('food_page', 1)
    food_page_obj = food_paginator.get_page(food_page)

    # Paginate drinks
    drink_paginator = Paginator(drinks, 6)
    drink_page = request.GET.get('drink_page', 1)
    drink_page_obj = drink_paginator.get_page(drink_page)

    return render(request, 'core/browse.html', {
        'foods': food_page_obj,
        'drinks': drink_page_obj,
        'all_dishes': dishes,  # for count
        'selected_category': category,
        'selected_role': role,
        'search_query': search_query,
        'total_count': dishes.count(),
        'dishes': food_page_obj,   # Keep backwards compatibility
    })

def about(request):
    return render(request, 'core/about.html')


def skin(request):
    active_category = request.GET.get('category', 'all')
    active_section  = request.GET.get('section', 'skin') 
    
    # Skin foods grouped
    grouped_skin = {}
    for food in SkinFood.objects.all().order_by('category', 'order'):
        grouped_skin.setdefault(food.category, []).append(food)

    # Wellness foods grouped
    grouped_wellness = {}
    for food in WellnessFood.objects.all().order_by('category', 'order'):
        grouped_wellness.setdefault(food.category, []).append(food)

    all_skin_foods     = SkinFood.objects.all()
    all_wellness_foods = WellnessFood.objects.all()

    return render(request, 'core/skin.html', {
        'grouped_foods':     grouped_skin,
        'grouped_wellness':  grouped_wellness,
        'skin_foods':        all_skin_foods,
        'wellness_foods':    all_wellness_foods,
        'active_category':   active_category,
        'active_section':    active_section,
        'categories':        SkinFood.CATEGORY_CHOICES,
        'wellness_cats':     WellnessFood.CATEGORY_CHOICES,
    })

def find_dishes(request):
    query_type        = request.GET.get('query_type', 'ingredients')
    ingredients_input = request.GET.get('ingredients', '')
    budget_input      = request.GET.get('budget', '')
    recent_food       = request.GET.get('recent_food', '')
    searched          = False
    results           = []
    comrade_results   = []

    SYNONYM_GROUPS = [
        {'sukuma', 'sukuma wiki', 'kales', 'collard greens', 'collard'},
        {'maize flour', 'unga wa mahindi', 'unga', 'ugali flour', 'cornmeal', 'maize meal'},
        {'wheat flour', 'unga wa ngano', 'all purpose flour', 'plain flour'},
        {'eggs', 'egg', 'mayai'},
        {'milk', 'maziwa', 'whole milk'},
        {'cooking oil', 'oil', 'mafuta'},
        {'onion', 'onions', 'vitunguu'},
        {'tomato', 'tomatoes', 'nyanya'},
        {'rice', 'wali'},
        {'beans', 'maharagwe'},
        {'potatoes', 'viazi'},
        {'sweet potatoes', 'viazi vitamu'},
        {'cabbage', 'kabeji'},
        {'salt', 'chumvi'},
        {'water', 'maji'},
        {'noodles', 'indomie', 'instant noodles'},
        {'beef', 'nyama ya ng\'ombe'},
        {'chicken', 'kuku'},
        {'fish', 'samaki'},
        {'sugar', 'sukari'},
        {'butter', 'siagi'},
        {'garlic', 'kitunguu saumu'},
        {'ginger', 'tangawizi'},
    ]

    def get_synonyms(term):
        """Return the full synonym set for a term, or just {term} if no group found."""
        t = term.lower().strip()
        for group in SYNONYM_GROUPS:
            if t in group:
                return group
        # Also check if term is a substring match for a group member
        for group in SYNONYM_GROUPS:
            for member in group:
                if t == member:
                    return group
        return {t}

    def ingredient_in_text(user_ing, text):
        """
        True only if user_ing (or a true synonym) appears as a meaningful
        word/phrase in text. Uses word-boundary logic to avoid
        'flour' matching 'wheat flour' when user meant 'maize flour'.
        """
        text_lower = text.lower()
        synonyms   = get_synonyms(user_ing)

        for variant in synonyms:
            if variant in text_lower:
                if variant == 'flour':
                    import re
                    if re.search(r'(wheat|plain|all.?purpose|self.?raising)\s+flour', text_lower):
                        continue   # it's wheat flour, skip
                return True
        return False

    def score_dish(dish_text, dish_ingredients_list, ingredient_list):
        """
        Returns (match_count, coverage, matched_ingredients) or None if dish
        doesn't actually contain ANY of the user's ingredients.
        """
        total = len(dish_ingredients_list) if dish_ingredients_list else 1

        matched_user_ings = []
        for u_ing in ingredient_list:
            if ingredient_in_text(u_ing, dish_text):
                matched_user_ings.append(u_ing)

        if not matched_user_ings:
            return None  # dish has NONE of the user's ingredients → skip entirely

        # Coverage = how many of the dish's own ingredients the user has
        user_has_count = sum(
            1 for d_ing in dish_ingredients_list
            if any(ingredient_in_text(u_ing, d_ing) for u_ing in ingredient_list)
        )
        coverage = user_has_count / total

        return (len(matched_user_ings), coverage, matched_user_ings)

    if request.GET.get('ingredients') or request.GET.get('budget'):
        searched = True
        dishes   = Dish.objects.all()

        # Exclude recently eaten
        if recent_food:
            for item in [r.strip().lower() for r in recent_food.split(',') if r.strip()]:
                synonyms = get_synonyms(item)
                for variant in synonyms:
                    if variant:
                        dishes = dishes.exclude(name__icontains=variant)

        # UDGET mode 
        if query_type == 'budget' and budget_input:
            try:
                budget = float(budget_input)
                dishes = dishes.filter(estimated_cost__lte=budget)
                comrade_results = list(
                    ComradeMeal.objects
                    .filter(total_cost_ksh__lte=int(budget))
                    .order_by('total_cost_ksh')[:6]
                )
            except ValueError:
                pass
            results = list(dishes[:12])

        # INGREDIENTS mode 
        elif query_type == 'ingredients' and ingredients_input:
            ingredient_list = [
                i.strip().lower()
                for i in ingredients_input.split(',') if i.strip()
            ]

            # Broad pre-filter: at least one synonym must appear somewhere in the dish
            q = Q()
            for ing in ingredient_list:
                for variant in get_synonyms(ing):
                    if variant:
                        q |= Q(ingredients__icontains=variant)
                        q |= Q(name__icontains=variant)
                        q |= Q(description__icontains=variant)
            dishes = dishes.filter(q)

            # Score and strictly filter
            tier1 = []  # has ALL user ingredients
            tier2 = []  # has MOST (≥50%)
            tier3 = []  # has at least ONE

            for dish in dishes:
                dish_ings  = [i.strip().lower() for i in dish.ingredients.split(',') if i.strip()]
                dish_text  = f"{dish.name} {dish.ingredients} {dish.description}".lower()

                scored = score_dish(dish_text, dish_ings, ingredient_list)
                if scored is None:
                    continue  # truly doesn't match — skip

                match_count, coverage, matched = scored
                total_user = len(ingredient_list)
                match_ratio = match_count / total_user  # how many of USER's ings match

                entry = (match_count, coverage, dish)

                if match_ratio == 1.0:
                    tier1.append(entry)          # has every ingredient user listed
                elif match_ratio >= 0.5:
                    tier2.append(entry)          # has half or more
                else:
                    tier3.append(entry)          # has at least one

            # Sort each tier by coverage desc, then take top results
            for tier in (tier1, tier2, tier3):
                tier.sort(key=lambda x: (x[0], x[1]), reverse=True)

            # Build final list: tier1 first, then tier2, then tier3
            seen = set()
            ordered = []
            for tier in (tier1, tier2, tier3):
                for match_count, coverage, dish in tier:
                    if dish.pk not in seen:
                        seen.add(dish.pk)
                        ordered.append(dish)
                if len(ordered) >= 12:
                    break

            results = ordered[:12]

            # Comrade meals
            comrade_q = Q()
            for ing in ingredient_list:
                for variant in get_synonyms(ing):
                    if variant:
                        comrade_q |= Q(kitchen_items_needed__icontains=variant)
                        comrade_q |= Q(name__icontains=variant)
                        comrade_q |= Q(description__icontains=variant)

            comrade_dishes = ComradeMeal.objects.filter(comrade_q).distinct()

            c_tier1, c_tier2, c_tier3 = [], [], []

            for meal in comrade_dishes:
                items_list   = meal.get_items() or []
                kitchen_text = meal.kitchen_items_needed or ''
                items_text   = ' '.join(item.get('item', '') for item in items_list)
                full_text    = f"{meal.name} {kitchen_text} {items_text}".lower()
                meal_ings    = (
                    [item.get('item', '').lower() for item in items_list] +
                    [k.strip().lower() for k in kitchen_text.split(',') if k.strip()]
                )

                scored = score_dish(full_text, meal_ings, ingredient_list)
                if scored is None:
                    continue

                match_count, coverage, matched = scored
                match_ratio = match_count / len(ingredient_list)
                entry = (match_count, coverage, meal)

                if match_ratio == 1.0:
                    c_tier1.append(entry)
                elif match_ratio >= 0.5:
                    c_tier2.append(entry)
                else:
                    c_tier3.append(entry)

            seen_c = set()
            ordered_c = []
            for tier in (c_tier1, c_tier2, c_tier3):
                tier.sort(key=lambda x: (x[0], x[1]), reverse=True)
                for match_count, coverage, meal in tier:
                    if meal.pk not in seen_c:
                        seen_c.add(meal.pk)
                        ordered_c.append(meal)
                if len(ordered_c) >= 6:
                    break

            comrade_results = ordered_c[:6]

    return render(request, 'core/find_dishes.html', {
        'results':           results,
        'comrade_results':   comrade_results,
        'searched':          searched,
        'ingredients_input': ingredients_input,
        'budget_input':      budget_input,
        'recent_food':       recent_food,
        'query_type':        query_type,
    })

def dish_detail(request, pk):
    dish               = get_object_or_404(Dish, pk=pk)
    recommended_foods  = Dish.objects.filter(name__in=dish.best_with_foods)
    recommended_drinks = Dish.objects.filter(name__in=dish.best_with_drinks)

    return render(request, 'core/dish_detail.html', {
        'dish':               dish,
        'recommended_foods':  recommended_foods,
        'recommended_drinks': recommended_drinks,
    })


def gym(request):
    category       = request.GET.get('category', 'all')
    search         = request.GET.get('search', '')
    timing_filter  = request.GET.get('timing', '')

    foods = GymFood.objects.all()

    if category and category != 'all':
        foods = foods.filter(category=category)

    if search:
        foods = (
            foods.filter(name__icontains=search) |
            foods.filter(description__icontains=search)
        )

    if timing_filter:
        foods = foods.filter(timing=timing_filter)

    return render(request, 'core/gym.html', {
        'foods':          foods,
        'active_category': category,
        'active_timing':  timing_filter,
        'search_query':   search,
        'categories':     GymFood.CATEGORY_CHOICES,
        'timings':        GymFood.TIMING_CHOICES,
    })

def comrade_kitchen(request):
    budget            = request.GET.get('budget', '').strip()
    ingredients_input = request.GET.get('ingredients', '').strip()
    recent_food       = request.GET.get('recent', '').strip()
    search_mode       = request.GET.get('mode', 'budget')
    active_category   = request.GET.get('category', '')
    searched          = False
    suggested_meals   = []
    comrade_food_suggestions = []
    affordable_items  = []
    budget_int        = None

    SYNONYMS = {
        'mayai': ['eggs', 'egg', 'mayai'],
        'eggs': ['eggs', 'egg', 'mayai'],
        'egg': ['eggs', 'egg', 'mayai'],
        'sukuma': ['sukuma', 'kales', 'sukuma wiki', 'collard'],
        'sukuma wiki': ['sukuma', 'kales', 'sukuma wiki', 'collard'],
        'kales': ['sukuma', 'kales', 'sukuma wiki'],
        'unga': ['maize', 'unga', 'ugali', 'flour', 'corn'],
        'maize flour': ['maize', 'unga', 'ugali', 'flour', 'corn', 'maize flour'],
        'maize': ['maize', 'unga', 'ugali', 'flour'],
        'ugali': ['ugali', 'unga', 'maize', 'maize flour'],
        'noodles': ['noodles', 'indomie', 'instant'],
        'indomie': ['noodles', 'indomie', 'instant'],
        'githeri': ['githeri', 'beans', 'maize'],
        'dengu': ['ndengu', 'dengu', 'grams', 'green grams'],
        'ndengu': ['ndengu', 'dengu', 'grams', 'green grams'],
        'beans': ['beans', 'maharagwe'],
        'maharagwe': ['beans', 'maharagwe'],
        'rice': ['rice', 'wali'],
        'wali': ['rice', 'wali'],
        'tomatoes': ['tomatoes', 'tomato', 'nyanya'],
        'tomato': ['tomatoes', 'tomato', 'nyanya'],
        'nyanya': ['tomatoes', 'tomato', 'nyanya'],
        'onion': ['onion', 'onions', 'vitunguu'],
        'onions': ['onion', 'onions', 'vitunguu'],
        'vitunguu': ['onion', 'onions', 'vitunguu'],
        'oil': ['oil', 'mafuta', 'cooking oil'],
        'cooking oil': ['oil', 'mafuta', 'cooking oil'],
        'mafuta': ['oil', 'mafuta', 'cooking oil'],
        'cabbage': ['cabbage', 'kabeji'],
        'kabeji': ['cabbage', 'kabeji'],
        'potatoes': ['potatoes', 'viazi'],
        'viazi': ['potatoes', 'viazi'],
        'salt': ['salt', 'chumvi'],
        'chumvi': ['salt', 'chumvi'],
        'water': ['water', 'maji'],
        'maji': ['water', 'maji'],
        'chapati': ['chapati', 'chapatti'],
        'beef': ['beef', 'nyama', "ng'ombe"],
        'chicken': ['chicken', 'kuku'],
        'fish': ['fish', 'samaki'],
        'milk': ['milk', 'maziwa'],
        'maziwa': ['milk', 'maziwa'],
        'sugar': ['sugar', 'sukari'],
        'sukari': ['sugar', 'sukari'],
        'porridge': ['porridge', 'uji'],
        'uji': ['porridge', 'uji'],
    }

    def expand_term(term):
        t = term.lower().strip()
        result = {t}
        result.update(t.split())
        for key, syns in SYNONYMS.items():
            if t == key or t in syns:
                result.update(syns)
        return result

    def text_contains_ingredient(user_ing, text):
        text_lower = text.lower()
        text_clean = (
            text_lower
            .replace('(', ' ').replace(')', ' ')
            .replace(',', ' ').replace('&', ' ')
        )
        expanded = expand_term(user_ing)
        for variant in expanded:
            if variant in text_lower:
                return True
        for word in text_clean.split():
            word = word.strip()
            if len(word) < 3:
                continue
            for variant in expanded:
                if variant == word:
                    return True
                if len(variant) >= 4 and len(word) >= 4:
                    if variant in word or word in variant:
                        return True
        return False

    def term_matches_text(term, text):
        """Check if a single term matches any word/phrase in text."""
        text_lower = text.lower()
        for variant in expand_term(term):
            if variant and variant in text_lower:
                return True
        return False

    def fuzzy_exclude(meal, recent_terms):
        """
        Exclude a meal only if BOTH the base meal AND one of its stew options
        match what the user recently ate.

        - "Rice and Beans" → excludes Rice only when Beans stew is also matched
        - "Rice" alone → does NOT exclude Rice (user can have rice with a different stew)
        - Meals with no stew options are excluded on base meal match alone
        """
        meal_name = meal.name.lower()
        stew_options = list(meal.stew_options.all())
        stew_names = [s.name.lower() for s in stew_options]

        base_matched = False
        stew_matched_names = []  # which stews from recent_terms matched

        for term in recent_terms:
            if term_matches_text(term, meal_name):
                base_matched = True
            for stew_name in stew_names:
                if term_matches_text(term, stew_name):
                    stew_matched_names.append(stew_name)

        if not base_matched:
            return False  # recent food doesn't mention this meal at all

        if not stew_names:
            return True  # standalone meal (no stew options), exclude it

        if stew_matched_names:
            return True  # user had this meal + a specific stew → exclude

        # Base meal matched but no specific stew matched →
        # Don't exclude — user can have this meal with a different stew
        return False

    def get_excluded_stew_names(meal, recent_terms):
        """Return set of stew names the user recently had with this meal."""
        stew_options = list(meal.stew_options.all())
        excluded = set()
        for term in recent_terms:
            for stew in stew_options:
                if term_matches_text(term, stew.name.lower()):
                    excluded.add(stew.name.lower())
        return excluded

    def build_meal_entry(meal, user_ingredients, budget_remaining=None, recent_terms=None):
        """Build a full entry dict for a ComradeMeal, including stew options."""
        items_list = meal.get_items() or []
        savings = 0
        items_user_has = []
        items_to_buy = []

        for item in items_list:
            item_name = item.get('item', '')
            item_cost = item.get('cost', 0)
            user_has = (
                any(text_contains_ingredient(ing, item_name) for ing in user_ingredients)
                if user_ingredients else False
            )
            if user_has:
                savings += item_cost
                items_user_has.append(item)
            else:
                items_to_buy.append(item)

        kitchen_user_has = []
        kitchen_needed = []
        for k in meal.get_kitchen_items() or []:
            if user_ingredients and any(text_contains_ingredient(ing, k) for ing in user_ingredients):
                kitchen_user_has.append(k)
            else:
                kitchen_needed.append(k)

        adjusted_cost = max(0, meal.total_cost_ksh - savings)

        full_text = ' '.join(filter(None, [
            meal.name,
            meal.kitchen_items_needed or '',
            ' '.join(item.get('item', '') for item in items_list),
        ])).lower()

        matched_ings = (
            [ing for ing in user_ingredients if text_contains_ingredient(ing, full_text)]
            if user_ingredients else []
        )
        match_ratio = len(matched_ings) / len(user_ingredients) if user_ingredients else 0

        # ── Stew options ──────────────────────────────────────────────────
        all_stews = list(meal.stew_options.all())

        # Filter out stews the user recently had with this meal
        excluded_stews = get_excluded_stew_names(meal, recent_terms) if recent_terms else set()
        available_stews = [s for s in all_stews if s.name.lower() not in excluded_stews]

        # Budget-aware stew filtering
        if budget_remaining is not None:
            affordable_stews = [
                s for s in available_stews
                if float(s.estimated_cost) <= budget_remaining
            ]
        else:
            affordable_stews = available_stews

        # Annotate each stew with total cost (meal base + stew)
        stews_with_total = [
            {
                'stew': s,
                'stew_cost': float(s.estimated_cost),
                'total_cost': meal.total_cost_ksh + float(s.estimated_cost),
                'recently_eaten': s.name.lower() in excluded_stews,
            }
            for s in all_stews
        ]

        return {
            'meal': meal,
            'original_cost': meal.total_cost_ksh,
            'adjusted_cost': adjusted_cost,
            'savings': savings,
            'items_user_has': items_user_has,
            'items_to_buy': items_to_buy,
            'kitchen_items_user_has': kitchen_user_has,
            'kitchen_items_needed': kitchen_needed,
            'match_score': len(matched_ings),
            'match_ratio': match_ratio,
            'match_label': (
                'full' if match_ratio == 1.0
                else 'most' if match_ratio >= 0.5
                else 'some'
            ),
            'tier_label': 'default',
            # Stew option data
            'all_stews': stews_with_total,          # all stews with total cost annotation
            'available_stews': affordable_stews,    # stews not recently eaten + within budget
            'has_stew_options': len(all_stews) > 0,
            'excluded_stews': excluded_stews,
        }

    # ── PARSE INPUTS ──────────────────────────────────────────────────────
    if budget or ingredients_input:
        searched = True

        user_ingredients = (
            [i.strip().lower() for i in ingredients_input.split(',') if i.strip()]
            if ingredients_input else []
        )

        if budget:
            try:
                budget_int = int(budget)
            except ValueError:
                pass

        recent_terms = (
            [r.strip() for r in recent_food.replace(' and ', ',').split(',') if r.strip()]
            if recent_food else []
        )

        # ── MODE 1: BUDGET ONLY ───────────────────────────────────────────
        if search_mode == 'budget' and budget_int is not None:
            for meal in ComradeMeal.objects.prefetch_related('stew_options').order_by('total_cost_ksh'):
                if meal.total_cost_ksh > budget_int:
                    continue
                if recent_terms and fuzzy_exclude(meal, recent_terms):
                    continue
                budget_remaining = budget_int - meal.total_cost_ksh
                entry = build_meal_entry(meal, [], budget_remaining=budget_remaining, recent_terms=recent_terms)
                entry['tier_label'] = 'budget_only'
                suggested_meals.append(entry)

            affordable_items = ComradeFood.objects.filter(
                price_ksh__lte=budget_int
            ).order_by('price_ksh')

        # ── MODE 2: INGREDIENTS ONLY ──────────────────────────────────────
        elif search_mode == 'ingredients' and user_ingredients:
            tier1, tier2, tier3 = [], [], []

            for meal in ComradeMeal.objects.prefetch_related('stew_options').all():
                if recent_terms and fuzzy_exclude(meal, recent_terms):
                    continue
                full_text = ' '.join(filter(None, [
                    meal.name,
                    meal.kitchen_items_needed or '',
                    ' '.join(item.get('item', '') for item in (meal.get_items() or [])),
                ])).lower()
                matched_ings = [
                    ing for ing in user_ingredients
                    if text_contains_ingredient(ing, full_text)
                ]
                if not matched_ings:
                    continue
                entry = build_meal_entry(meal, user_ingredients, recent_terms=recent_terms)
                match_ratio = entry['match_ratio']
                if match_ratio == 1.0:
                    entry['tier_label'] = 'full_match'
                    tier1.append(entry)
                elif match_ratio >= 0.5:
                    entry['tier_label'] = 'most_match'
                    tier2.append(entry)
                else:
                    entry['tier_label'] = 'some_match'
                    tier3.append(entry)

            for tier in (tier1, tier2, tier3):
                tier.sort(key=lambda x: x['match_score'], reverse=True)
            suggested_meals = tier1 + tier2 + tier3

        # ── MODE 3: BUDGET + INGREDIENTS ─────────────────────────────────
        elif search_mode == 'both':
            tier_a, tier_b, tier_c = [], [], []

            for meal in ComradeMeal.objects.prefetch_related('stew_options').all():
                if recent_terms and fuzzy_exclude(meal, recent_terms):
                    continue
                budget_remaining = (budget_int - meal.total_cost_ksh) if budget_int else None
                entry = build_meal_entry(meal, user_ingredients, budget_remaining=budget_remaining, recent_terms=recent_terms)
                adjusted_cost    = entry['adjusted_cost']
                matched_ings_count = entry['match_score']
                original_cost    = entry['original_cost']

                if budget_int is not None:
                    over_budget_originally = original_cost > budget_int
                    within_after_savings   = adjusted_cost <= budget_int

                    if over_budget_originally and within_after_savings and matched_ings_count > 0:
                        entry['tier_label'] = 'ingredients_unlock'
                        tier_a.append(entry)
                    elif adjusted_cost <= budget_int:
                        if matched_ings_count > 0:
                            entry['tier_label'] = 'within_budget_match'
                            tier_b.append(entry)
                        else:
                            entry['tier_label'] = 'budget_only'
                            tier_c.append(entry)
                else:
                    if matched_ings_count > 0:
                        entry['tier_label'] = 'within_budget_match'
                        tier_b.append(entry)
                    else:
                        entry['tier_label'] = 'budget_only'
                        tier_c.append(entry)

            tier_a.sort(key=lambda x: (x['match_score'], -x['adjusted_cost']), reverse=True)
            tier_b.sort(key=lambda x: (x['match_score'], -x['adjusted_cost']), reverse=True)
            tier_c.sort(key=lambda x: x['adjusted_cost'])
            suggested_meals = tier_a + tier_b + tier_c

            affordable_items = (
                ComradeFood.objects.filter(price_ksh__lte=budget_int).order_by('price_ksh')
                if budget_int else []
            )

    # ── STATIC CONTEXT ────────────────────────────────────────────────────
    featured_meals = ComradeMeal.objects.prefetch_related('stew_options').order_by('total_cost_ksh')[:8]
    all_foods = ComradeFood.objects.all().order_by('price_ksh')
    if active_category:
        all_foods = all_foods.filter(category=active_category)

    comrade_foods_display = (
        ComradeFood.objects
        .filter(category=active_category) if active_category
        else ComradeFood.objects.all()
    ).order_by('price_ksh')

    stock_items = [
        {'item': 'Rice', 'qty': '4kg', 'tip': 'Lasts ~3 months for one person', 'price': 'Ksh 520', 'unit_price': '130/kg'},
        {'item': 'Indomie (full box)', 'qty': '40 packets', 'tip': 'Instant meal any time. Add an egg to make it filling.', 'price': 'Ksh 400', 'unit_price': '10/packet'},
        {'item': 'Maize Flour (Unga)', 'qty': '2kg', 'tip': 'Ugali base — most filling food per shilling', 'price': 'Ksh 160', 'unit_price': '80/kg'},
        {'item': 'Cooking Oil', 'qty': '1 litre', 'tip': 'Essential for every single meal. Never run out.', 'price': 'Ksh 250', 'unit_price': '250/L'},
        {'item': 'Eggs (tray)', 'qty': '30 eggs', 'tip': '10 full breakfasts at Ksh 45 each.', 'price': 'Ksh 450', 'unit_price': '15/egg'},
        {'item': 'Onions', 'qty': '1kg', 'tip': 'Base for almost every Kenyan dish. Long shelf life.', 'price': 'Ksh 60', 'unit_price': '60/kg'},
        {'item': 'Garlic', 'qty': '250g', 'tip': 'Lasts weeks. Huge flavour boost.', 'price': 'Ksh 50', 'unit_price': '200/kg'},
        {'item': 'Milk (500ml packets)', 'qty': '10-pack box', 'tip': 'Tea and porridge sorted for a week.', 'price': 'Ksh 500', 'unit_price': '50/packet'},
        {'item': 'Ndengu (Green Grams)', 'qty': '1kg', 'tip': 'Complete protein, cheap, cooks in 30 mins.', 'price': 'Ksh 130', 'unit_price': '130/kg'},
        {'item': 'Beans (Maharagwe)', 'qty': '1kg', 'tip': 'Hearty, filling, nutritious.', 'price': 'Ksh 120', 'unit_price': '120/kg'},
        {'item': 'Njahi (Black Beans)', 'qty': '1kg', 'tip': 'Rich in iron. Long shelf life.', 'price': 'Ksh 150', 'unit_price': '150/kg'},
        {'item': 'Kamande (Lentils)', 'qty': '1kg', 'tip': 'Fast cooking (no soaking). Very filling.', 'price': 'Ksh 140', 'unit_price': '140/kg'},
        {'item': 'Porridge Flour (Uji)', 'qty': '1kg', 'tip': 'Quick filling breakfast.', 'price': 'Ksh 80', 'unit_price': '80/kg'},
        {'item': 'Sugar', 'qty': '1kg', 'tip': 'For tea, porridge, beverages. Always have some.', 'price': 'Ksh 130', 'unit_price': '130/kg'},
        {'item': 'Wheat Flour', 'qty': '2kg', 'tip': 'Chapati, pancakes, mandazi. Versatile and cheap.', 'price': 'Ksh 160', 'unit_price': '80/kg'},
        {'item': 'Salt', 'qty': '1kg', 'tip': 'Never cook without it. Lasts months.', 'price': 'Ksh 30', 'unit_price': '30/kg'},
        {'item': 'Tomato Paste (tins)', 'qty': '3 tins', 'tip': 'Flavour base for stews. Cheaper than fresh tomatoes.', 'price': 'Ksh 90', 'unit_price': '30/tin'},
    ]

    return render(request, 'core/comrade_kitchen.html', {
        'searched':               searched,
        'suggested_meals':        suggested_meals,
        'comrade_food_suggestions': comrade_food_suggestions,
        'affordable_items':       affordable_items,
        'featured_meals':         featured_meals,
        'all_foods':              all_foods,
        'comrade_foods_display':  comrade_foods_display,
        'active_category':        active_category,
        'search_mode':            search_mode,
        'budget':                 budget,
        'budget_int':             budget_int,
        'ingredients_input':      ingredients_input,
        'recent_food':            recent_food,
        'tips':                   [],
        'stock_items':            stock_items,
    })

def comrade_food_detail(request, pk):
    food = get_object_or_404(ComradeFood, pk=pk)
    return render(request, 'core/comrade_food_detail.html', {
        'food': food,
    })

#  handles camera, voice and text input
@require_POST
def ai_scan_ajax(request):
    from .ai_engine import suggest_from_voice, suggest_meals_from_image, suggest_meals_from_ingredients
    input_type = request.POST.get('input_type')
    try:
        if input_type == 'text':
            ingredients_raw = request.POST.get('ingredients', '').strip()
            ingredients = [i.strip() for i in ingredients_raw.split(',') if i.strip()]
            result = suggest_meals_from_ingredients(ingredients) if ingredients else 'Please enter some ingredients.'
        elif input_type == 'voice':
            transcript = request.POST.get('transcript', '').strip()
            result = suggest_from_voice(transcript) if transcript else 'No speech detected.'
        elif input_type == 'camera':
            image_file = request.FILES.get('image')
            result = suggest_meals_from_image(image_file.read()) if image_file else 'No image received.'
        else:
            result = 'Unknown input type.'
        return JsonResponse({'result': result})

    except Exception as e:
        error_str = str(e)
        # Clean quota error message
        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
            return JsonResponse({'error': '⚠️ AI is busy right now, free tier limit reached. Please try again in a minute or two.'})
        elif '404' in error_str or 'not found' in error_str.lower():
            return JsonResponse({'error': '⚠️ AI model unavailable. Please try again shortly.'})
        else:
            return JsonResponse({'error': f'⚠️ AI unavailable. Please try again. ({error_str[:80]})'})