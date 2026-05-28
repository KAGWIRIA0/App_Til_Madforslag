from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Dish, GymFood, ComradeFood, ComradeMeal, ComradeMealStewOption, SkinFood, WellnessFood
from .ai_engine import suggest_from_voice, suggest_meals_from_image, suggest_meals_from_ingredients
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
        'all_dishes': dishes,
        'selected_category': category,
        'selected_role': role,
        'search_query': search_query,
        'total_count': dishes.count(),
        'dishes': food_page_obj,
    })


def about(request):
    return render(request, 'core/about.html')


def skin(request):
    active_category = request.GET.get('category', 'all')
    active_section  = request.GET.get('section', 'skin')

    grouped_skin = {}
    for food in SkinFood.objects.all().order_by('category', 'order'):
        grouped_skin.setdefault(food.category, []).append(food)

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
        t = term.lower().strip()
        for group in SYNONYM_GROUPS:
            if t in group:
                return group
        for group in SYNONYM_GROUPS:
            for member in group:
                if t == member:
                    return group
        return {t}

    def ingredient_in_text(user_ing, text):
        text_lower = text.lower()
        synonyms   = get_synonyms(user_ing)
        for variant in synonyms:
            if variant in text_lower:
                if variant == 'flour':
                    import re
                    if re.search(r'(wheat|plain|all.?purpose|self.?raising)\s+flour', text_lower):
                        continue
                return True
        return False

    def score_dish(dish_text, dish_ingredients_list, ingredient_list):
        total = len(dish_ingredients_list) if dish_ingredients_list else 1
        matched_user_ings = []
        for u_ing in ingredient_list:
            if ingredient_in_text(u_ing, dish_text):
                matched_user_ings.append(u_ing)
        if not matched_user_ings:
            return None
        user_has_count = sum(
            1 for d_ing in dish_ingredients_list
            if any(ingredient_in_text(u_ing, d_ing) for u_ing in ingredient_list)
        )
        coverage = user_has_count / total
        return (len(matched_user_ings), coverage, matched_user_ings)

    if request.GET.get('ingredients') or request.GET.get('budget'):
        searched = True
        dishes   = Dish.objects.all()

        if recent_food:
            for item in [r.strip().lower() for r in recent_food.split(',') if r.strip()]:
                synonyms = get_synonyms(item)
                for variant in synonyms:
                    if variant:
                        dishes = dishes.exclude(name__icontains=variant)

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

        elif query_type == 'ingredients' and ingredients_input:
            ingredient_list = [
                i.strip().lower()
                for i in ingredients_input.split(',') if i.strip()
            ]
            q = Q()
            for ing in ingredient_list:
                for variant in get_synonyms(ing):
                    if variant:
                        q |= Q(ingredients__icontains=variant)
                        q |= Q(name__icontains=variant)
                        q |= Q(description__icontains=variant)
            dishes = dishes.filter(q)

            tier1 = []
            tier2 = []
            tier3 = []

            for dish in dishes:
                dish_ings  = [i.strip().lower() for i in dish.ingredients.split(',') if i.strip()]
                dish_text  = f"{dish.name} {dish.ingredients} {dish.description}".lower()
                scored = score_dish(dish_text, dish_ings, ingredient_list)
                if scored is None:
                    continue
                match_count, coverage, matched = scored
                total_user = len(ingredient_list)
                match_ratio = match_count / total_user
                entry = (match_count, coverage, dish)
                if match_ratio == 1.0:
                    tier1.append(entry)
                elif match_ratio >= 0.5:
                    tier2.append(entry)
                else:
                    tier3.append(entry)

            for tier in (tier1, tier2, tier3):
                tier.sort(key=lambda x: (x[0], x[1]), reverse=True)

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
        'foods':           foods,
        'active_category': category,
        'active_timing':   timing_filter,
        'search_query':    search,
        'categories':      GymFood.CATEGORY_CHOICES,
        'timings':         GymFood.TIMING_CHOICES,
    })



_SYNONYMS = {
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
    'beef': ['beef', 'nyama', "ng'ombe", 'meat'],
    'meat': ['meat', 'beef', 'nyama', "ng'ombe"],
    'chicken': ['chicken', 'kuku'],
    'kuku': ['chicken', 'kuku'],
    'fish': ['fish', 'samaki'],
    'samaki': ['fish', 'samaki'],
    'milk': ['milk', 'maziwa'],
    'maziwa': ['milk', 'maziwa'],
    'sugar': ['sugar', 'sukari'],
    'sukari': ['sugar', 'sukari'],
    'porridge': ['porridge', 'uji'],
    'uji': ['porridge', 'uji'],
    'tilapia': ['tilapia', 'fish', 'samaki'],
    'omena': ['omena', 'dagaa', 'fish'],
    'sardines': ['sardines', 'omena', 'dagaa'],
    'sausage': ['sausage', 'sausages', 'sosej'],
    'smokie': ['smokie', 'smokies', 'sausage'],
    'spinach': ['spinach', 'mchicha'],
    'mchicha': ['spinach', 'mchicha'],
    'terere': ['terere', 'amaranth'],
    'ndengu stew': ['ndengu', 'dengu', 'green grams'],
    'green grams': ['ndengu', 'dengu', 'green grams', 'grams'],
    'kamande': ['kamande', 'lentils'],
    'lentils': ['lentils', 'kamande'],
    'peas': ['peas', 'minji', 'green peas'],
    'minji': ['peas', 'minji', 'green peas'],
}


def _expand_term(term):
    """Return all synonym variants for a term."""
    t = term.lower().strip()
    result = {t}
    result.update(t.split())
    for key, syns in _SYNONYMS.items():
        if t == key or t in syns:
            result.update(syns)
    return result


def _text_has_term(term, text):
    """Return True if term (or any synonym) appears in text."""
    text_lower = text.lower()
    for variant in _expand_term(term):
        if variant and variant in text_lower:
            return True
    return False




def _parse_recent_pairs(recent_food_str):
    """
    Parse the "eaten recently" string into a list of (base_term, stew_term_or_None) tuples.

    Examples
    --------
    "Rice and Beans, Ugali and Sukuma, Chapati"
      → [('rice', 'beans'), ('ugali', 'sukuma'), ('chapati', None)]

    "Rice, Beans"  — comma-separated without "and"
      → [('rice', None), ('beans', None)]

    "Rice Beans"   — space only (treated as single entry, no stew)
      → [('rice beans', None)]
    """
    if not recent_food_str:
        return []

    pairs = []
    # Split on commas first
    entries = [e.strip() for e in recent_food_str.split(',') if e.strip()]
    for entry in entries:
        # Each entry may be "Base and Stew"
        if ' and ' in entry.lower():
            parts = entry.lower().split(' and ', 1)
            base  = parts[0].strip()
            stew  = parts[1].strip()
            pairs.append((base, stew))
        else:
            pairs.append((entry.lower().strip(), None))
    return pairs


def _should_exclude_meal(meal, recent_pairs):
    """
    Decide whether an entire ComradeMeal should be EXCLUDED from results.

    Rules
    -----
    • If the user says "Rice and Beans":
        - Rice (base) matches → check if "Beans" matches any stew option.
        - If the meal has NO stew options AND base matches → exclude it.
        - If the meal HAS stew options and ALL of them are in recent_pairs → exclude it.
        - If only SOME stews match → keep the meal (those stews will be greyed out).

    • If the user says "Rice" (no stew specified):
        - If the meal has stew options → KEEP IT (different stew today is fine).
        - If the meal has NO stew options → exclude it.

    • A meal is also excluded if EVERY one of its stew options has been eaten recently.
    """
    meal_name_lower  = meal.name.lower()
    stew_options     = list(meal.stew_options.all())

    for base_term, stew_term in recent_pairs:
        base_matches = _text_has_term(base_term, meal_name_lower)
        if not base_matches:
            continue

        # Base meal matches the recent entry
        if not stew_options:
            # No stew choices → this is a standalone meal → exclude it
            return True

        if stew_term is None:
            # User mentioned the base only (e.g. "Rice") → keep if stew options exist
            continue

        # User specified both base + stew (e.g. "Rice and Beans")
        # Exclude ONLY if the specific stew matches one of the stew options
        for stew in stew_options:
            if _text_has_term(stew_term, stew.name.lower()):
                # That exact combo was eaten — but we still keep the meal
                # unless ALL stews have been eaten. We handle that below.
                break

    # Final pass: exclude if ALL stew options have been eaten recently
    if stew_options:
        excluded_stew_names = _get_excluded_stew_names(meal, recent_pairs)
        if len(excluded_stew_names) >= len(stew_options):
            return True

    return False


def _get_excluded_stew_names(meal, recent_pairs):
    """
    Return the set of stew names (lowercased) that the user has eaten recently
    WITH this meal. These stews will be greyed out in the UI.

    A stew is excluded only when the user ate THIS meal + THIS stew together,
    i.e. their recent entry has both the base term (matching the meal name) AND
    the stew term (matching this stew's name).

    If the user typed just "Beans" (no base meal context), we do NOT grey out
    the Beans stew on the Rice card — because "Beans" alone is ambiguous.
    """
    excluded = set()
    if not recent_pairs:
        return excluded

    meal_name_lower = meal.name.lower()
    stew_options    = list(meal.stew_options.all())

    for base_term, stew_term in recent_pairs:
        if stew_term is None:
            # Entry like "Rice" — no stew mentioned → nothing to grey out
            continue

        base_matches = _text_has_term(base_term, meal_name_lower)
        if not base_matches:
            continue

        # Base matches — check which stew matches stew_term
        for stew in stew_options:
            if _text_has_term(stew_term, stew.name.lower()):
                excluded.add(stew.name.lower())

    return excluded


def _stew_match_score(stew, user_ingredients):
    """
    Return how many of the user's ingredients appear in this stew's name/ingredients.
    Used to sort stews so user-matching ones appear first.
    """
    if not user_ingredients:
        return 0
    stew_text = f"{stew.name} {stew.ingredients}".lower()
    return sum(1 for ing in user_ingredients if _text_has_term(ing, stew_text))


def _build_meal_entry(meal, user_ingredients, budget_remaining=None, recent_pairs=None):
    """
    Build the full context dict for a ComradeMeal card.

    Key improvements over original:
    - Uses _get_excluded_stew_names / _should_exclude_meal for correct greying.
    - Sorts stew options so user-ingredient matches float to the top.
    - Computes match score / savings correctly.
    """
    items_list       = meal.get_items() or []
    savings          = 0
    items_user_has   = []
    items_to_buy     = []

    for item in items_list:
        item_name = item.get('item', '')
        item_cost = item.get('cost', 0)
        user_has  = (
            any(_text_has_term(ing, item_name) for ing in user_ingredients)
            if user_ingredients else False
        )
        if user_has:
            savings += item_cost
            items_user_has.append(item)
        else:
            items_to_buy.append(item)

    kitchen_user_has = []
    kitchen_needed   = []
    for k in meal.get_kitchen_items() or []:
        if user_ingredients and any(_text_has_term(ing, k) for ing in user_ingredients):
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
        [ing for ing in user_ingredients if _text_has_term(ing, full_text)]
        if user_ingredients else []
    )
    match_ratio = len(matched_ings) / len(user_ingredients) if user_ingredients else 0

    # Stew options
    all_stews = list(meal.stew_options.all())

    # Which stews are greyed out (eaten recently WITH this meal)
    excluded_stew_names = _get_excluded_stew_names(meal, recent_pairs or [])

    # Available stews = not recently eaten + (optionally) within remaining budget
    available_stews = [s for s in all_stews if s.name.lower() not in excluded_stew_names]
    if budget_remaining is not None:
        available_stews = [
            s for s in available_stews
            if float(s.estimated_cost) <= budget_remaining
        ]

    # Sort: stews matching user's ingredients first, then alphabetically
    def stew_sort_key(stew):
        score = _stew_match_score(stew, user_ingredients)
        in_excluded = stew.name.lower() in excluded_stew_names
        # Higher score = higher priority; excluded (greyed) stews go last
        return (not in_excluded, score, stew.is_featured)

    all_stews_sorted = sorted(all_stews, key=stew_sort_key, reverse=True)

    stews_with_total = [
        {
            'stew':          s,
            'stew_cost':     float(s.estimated_cost),
            'total_cost':    meal.total_cost_ksh + float(s.estimated_cost),
            'recently_eaten': s.name.lower() in excluded_stew_names,
            'user_has_ingredients': _stew_match_score(s, user_ingredients) > 0,
        }
        for s in all_stews_sorted
    ]

    base_recently_eaten = any(
        _text_has_term(base_term, meal.name.lower())
        for base_term, _ in (recent_pairs or [])
    )

    all_stews_excluded = (
        len(all_stews) > 0 and
        len(excluded_stew_names) >= len(all_stews)
    )

    return {
        'meal':                    meal,
        'original_cost':           meal.total_cost_ksh,
        'adjusted_cost':           adjusted_cost,
        'savings':                 savings,
        'items_user_has':          items_user_has,
        'items_to_buy':            items_to_buy,
        'kitchen_items_user_has':  kitchen_user_has,
        'kitchen_items_needed':    kitchen_needed,
        'match_score':             len(matched_ings),
        'match_ratio':             match_ratio,
        'match_label': (
            'full' if match_ratio == 1.0
            else 'most' if match_ratio >= 0.5
            else 'some'
        ),
        'tier_label':              'default',
        # Stew data
        'all_stews':               stews_with_total,
        'available_stews':         available_stews,
        'has_stew_options':        len(all_stews) > 0,
        'excluded_stews':          excluded_stew_names,
        'suggest_other_stews':     base_recently_eaten and not all_stews_excluded and len(excluded_stew_names) > 0,
        'all_stews_excluded':      all_stews_excluded,
    }




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

        # Parse "eaten recently" into structured pairs
        recent_pairs = _parse_recent_pairs(recent_food)


        if search_mode == 'budget' and budget_int is not None:
            for meal in ComradeMeal.objects.prefetch_related('stew_options').order_by('total_cost_ksh'):
                if meal.total_cost_ksh > budget_int:
                    continue
                if recent_pairs and _should_exclude_meal(meal, recent_pairs):
                    continue
                budget_remaining = budget_int - meal.total_cost_ksh
                entry = _build_meal_entry(
                    meal, [],
                    budget_remaining=budget_remaining,
                    recent_pairs=recent_pairs,
                )
                entry['tier_label'] = 'budget_only'
                suggested_meals.append(entry)

            affordable_items = ComradeFood.objects.filter(
                price_ksh__lte=budget_int
            ).order_by('price_ksh')


        elif search_mode == 'ingredients' and user_ingredients:
            tier1, tier2, tier3 = [], [], []

            for meal in ComradeMeal.objects.prefetch_related('stew_options').all():
                if recent_pairs and _should_exclude_meal(meal, recent_pairs):
                    continue

                full_text = ' '.join(filter(None, [
                    meal.name,
                    meal.kitchen_items_needed or '',
                    ' '.join(item.get('item', '') for item in (meal.get_items() or [])),
                ])).lower()

                matched_ings = [
                    ing for ing in user_ingredients
                    if _text_has_term(ing, full_text)
                ]
                if not matched_ings:
                    continue

                entry = _build_meal_entry(meal, user_ingredients, recent_pairs=recent_pairs)
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


        elif search_mode == 'both':
            tier_a, tier_b, tier_c = [], [], []

            for meal in ComradeMeal.objects.prefetch_related('stew_options').all():
                if recent_pairs and _should_exclude_meal(meal, recent_pairs):
                    continue

                budget_remaining = (budget_int - meal.total_cost_ksh) if budget_int else None
                entry = _build_meal_entry(
                    meal, user_ingredients,
                    budget_remaining=budget_remaining,
                    recent_pairs=recent_pairs,
                )
                adjusted_cost      = entry['adjusted_cost']
                matched_ings_count = entry['match_score']
                original_cost      = entry['original_cost']

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
        'searched':                  searched,
        'suggested_meals':           suggested_meals,
        'comrade_food_suggestions':  comrade_food_suggestions,
        'affordable_items':          affordable_items,
        'featured_meals':            featured_meals,
        'all_foods':                 all_foods,
        'comrade_foods_display':     comrade_foods_display,
        'active_category':           active_category,
        'search_mode':               search_mode,
        'budget':                    budget,
        'budget_int':                budget_int,
        'ingredients_input':         ingredients_input,
        'recent_food':               recent_food,
        'tips':                      [],
        'stock_items':               stock_items,
    })


def comrade_food_detail(request, pk):
    food = get_object_or_404(ComradeFood, pk=pk)
    meal = food.meals.prefetch_related('stew_options').first()
    return render(request, 'core/comrade_food_detail.html', {
        'food': food,
        'meal': meal,
    })


@require_POST
def ai_scan_ajax(request):
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
        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
            return JsonResponse({'error': 'AI is busy right now, free tier limit reached. Please try again in a minute or two.'})
        elif '404' in error_str or 'not found' in error_str.lower():
            return JsonResponse({'error': 'AI model unavailable. Please try again shortly.'})
        else:
            return JsonResponse({'error': f'AI unavailable. Please try again. ({error_str[:80]})'})