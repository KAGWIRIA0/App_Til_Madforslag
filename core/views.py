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

    foods = dishes.filter(meal_type='food')
    drinks = dishes.filter(meal_type='drink')

    food_paginator = Paginator(foods, 6)
    food_page = request.GET.get('food_page', 1)
    food_page_obj = food_paginator.get_page(food_page)

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
        {'maize flour', 'unga wa mahindi', 'ugali flour', 'cornmeal', 'maize meal'},
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
        return {t}

    def ingredient_in_text(user_ing, text):
        text_lower = text.lower()
        synonyms   = get_synonyms(user_ing)
        for variant in synonyms:
            if variant and variant in text_lower:
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
                        # FIX: was incorrectly using undefined 'search_query'; use 'variant' instead
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



_SYNONYM_GROUPS = [
    frozenset(['maize flour', 'unga wa mahindi', 'ugali flour', 'cornmeal', 'maize meal']),
    frozenset(['wheat flour', 'unga wa ngano', 'all purpose flour', 'plain flour', 'chapati flour']),
    frozenset(['self raising flour', 'self-raising flour']),
    frozenset(['sukuma', 'sukuma wiki', 'kales', 'collard greens', 'collard', 'managu']),
    frozenset(['eggs', 'egg', 'mayai']),
    frozenset(['maize', 'mahindi']),
    frozenset(['milk', 'maziwa', 'whole milk']),
    frozenset(['cooking oil', 'mafuta', 'vegetable oil', 'oil']),
    frozenset(['onion', 'onions', 'vitunguu']),
    frozenset(['tomato', 'tomatoes', 'nyanya']),
    frozenset(['rice', 'wali']),
    frozenset(['beans', 'maharagwe']),
    frozenset(['potatoes', 'viazi', 'irish potatoes']),
    frozenset(['sweet potatoes', 'viazi vitamu']),
    frozenset(['cabbage', 'kabeji']),
    frozenset(['salt', 'chumvi']),
    frozenset(['water', 'maji']),
    frozenset(['noodles', 'indomie', 'instant noodles']),
    frozenset(['beef', "nyama ya ng'ombe", 'ngombe']),
    frozenset(['chicken', 'kuku']),
    frozenset(['fish', 'samaki']),
    frozenset(['sugar', 'sukari']),
    frozenset(['butter', 'siagi']),
    frozenset(['garlic', 'kitunguu saumu']),
    frozenset(['ginger', 'tangawizi']),
    frozenset(['chapati', 'chapatti']),
    frozenset(['ugali', 'ugali meal']),
    frozenset(['ndengu', 'dengu', 'green grams', 'ndengu stew']),
    frozenset(['kamande', 'lentils']),
    frozenset(['peas', 'minji', 'green peas']),
    frozenset(['spinach', 'mchicha']),
    frozenset(['terere', 'amaranth']),
    frozenset(['omena', 'dagaa']),
    frozenset(['tilapia']),
    frozenset(['porridge', 'uji']),
    frozenset(['meat', 'nyama']),
    frozenset(['sausage', 'sausages']),
    frozenset(['smokie', 'smokies']),
    frozenset(['carrots', 'carrot', 'karoti']),
]

_SYNONYM_MAP = {}
for _grp in _SYNONYM_GROUPS:
    for _term in _grp:
        _SYNONYM_MAP[_term.lower()] = _grp


def _get_synonyms(term):
    """Return all synonym variants for a term (including itself)."""
    t = term.lower().strip()
    if t in _SYNONYM_MAP:
        return _SYNONYM_MAP[t]
    return frozenset([t])


def _text_has_term(term, text):
    """
    Return True if term (or any synonym) appears in text as a whole word/phrase.
    Uses word-boundary checking to prevent cross-matches like
    'wheat flour' matching 'maize flour'.
    """
    text_lower = text.lower()
    for variant in _get_synonyms(term):
        if not variant:
            continue
        idx = text_lower.find(variant)
        while idx != -1:
            before_ok = (idx == 0) or (not text_lower[idx - 1].isalnum())
            end = idx + len(variant)
            after_ok = (end >= len(text_lower)) or (not text_lower[end].isalnum())
            if before_ok and after_ok:
                return True
            idx = text_lower.find(variant, idx + 1)
    return False


def _parse_recent_pairs(recent_food_str):
    """
    Parse the "eaten recently" string into (base_term, stew_term_or_None) tuples.

    "Rice and Beans, Ugali and Sukuma, Chapati"
      → [('rice', 'beans'), ('ugali', 'sukuma'), ('chapati', None)]

    "Ugali and Eggs"
      → [('ugali', 'eggs')]
      Excludes ONLY Ugali+Eggs. Ugali with other stews is still available.

    "Ugali"  (no stew qualifier)
      → [('ugali', None)]
      Excludes ALL Ugali meals — user doesn't want Ugali at all today.
    """
    if not recent_food_str:
        return []

    pairs = []
    entries = [e.strip() for e in recent_food_str.split(',') if e.strip()]
    for entry in entries:
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
    Decide whether a ComradeMeal should be excluded from results.

    Rules:
    - "Ugali and Eggs": exclude ONLY if ALL stew options have been eaten recently.
      If Ugali has other stews besides Eggs, it stays visible (Eggs greyed out).
    - "Ugali" (no stew): exclude ALL Ugali meals — user doesn't want Ugali today.
    - Standalone meals (no stew options) matching the base term are excluded.
    """
    meal_name_lower = meal.name.lower()
    stew_options    = list(meal.stew_options.all())

    for base_term, stew_term in recent_pairs:
        base_matches = _text_has_term(base_term, meal_name_lower)
        if not base_matches:
            continue

        if stew_term is None:
            # User said just "Ugali" or "Managu" — exclude entirely
            return True

        if not stew_options:
            # Standalone meal (no stew options) matching base → exclude
            return True

    # Final pass: exclude only if ALL stew options have been eaten recently
    if stew_options:
        excluded_stew_names = _get_excluded_stew_names(meal, recent_pairs)
        if len(excluded_stew_names) >= len(stew_options):
            return True

    return False


def _get_excluded_stew_names(meal, recent_pairs):
    """
    Return the set of stew names (lowercased) the user has eaten recently
    WITH this specific meal base. These stews will be greyed out in the UI.
    """
    excluded = set()
    if not recent_pairs:
        return excluded

    meal_name_lower = meal.name.lower()
    stew_options    = list(meal.stew_options.all())

    for base_term, stew_term in recent_pairs:
        if stew_term is None:
            continue

        base_matches = _text_has_term(base_term, meal_name_lower)
        if not base_matches:
            continue

        for stew in stew_options:
            if _text_has_term(stew_term, stew.name.lower()):
                excluded.add(stew.name.lower())

    return excluded


def _stew_match_score(stew, user_ingredients):
    """How many of the user's ingredients appear in this stew's name/ingredients."""
    if not user_ingredients:
        return 0
    stew_text = f"{stew.name} {getattr(stew, 'ingredients', '')}".lower()
    return sum(1 for ing in user_ingredients if _text_has_term(ing, stew_text))


def _stew_missing_ingredients(stew, user_ingredients):
    """
    Return stew ingredients the user does NOT have.
    Used for the "consider buying…" tip on the detail page.
    """
    raw = getattr(stew, 'ingredients', '') or ''
    if not raw:
        return []

    stew_ings = [i.strip() for i in raw.split(',') if i.strip()]
    missing = []
    for ing in stew_ings:
        user_has = any(_text_has_term(u_ing, ing) for u_ing in (user_ingredients or []))
        if not user_has:
            missing.append(ing)
    return missing


def _build_meal_entry(meal, user_ingredients, budget_int=None, recent_pairs=None):
    """
    Build the full context dict for a ComradeMeal card.

    Ingredient ticking:
    - Items the user has are ticked off, reducing the adjusted cost.
    - Each stew option shows ingredient match score and missing items.
    - The stew with the highest ingredient match (not recently eaten) is 'top_pick'.

    Budget logic:
    - base_within_budget: True if meal.total_cost_ksh <= budget_int (no stew needed).
    - Each stew: stew_affordable = True if base + stew_cost <= budget_int.
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

    # Base meal text only (no stew text) — prevents cross-flour matching
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

    # --- Stew options ---
    all_stews = list(meal.stew_options.all())
    excluded_stew_names = _get_excluded_stew_names(meal, recent_pairs or [])

    best_stew_score = -1
    top_pick_stew   = None

    stews_with_total = []
    for s in all_stews:
        stew_cost       = float(getattr(s, 'estimated_cost', 0) or 0)
        total_with_stew = meal.total_cost_ksh + stew_cost
        recently_eaten  = s.name.lower() in excluded_stew_names
        ing_score       = _stew_match_score(s, user_ingredients)
        missing_ings    = _stew_missing_ingredients(s, user_ingredients)

        if budget_int is not None:
            stew_affordable = (total_with_stew <= budget_int)
        else:
            stew_affordable = True

        stews_with_total.append({
            'stew':                  s,
            'stew_cost':             stew_cost,
            'total_cost':            total_with_stew,
            'recently_eaten':        recently_eaten,
            'user_has_ingredients':  ing_score > 0,
            'ingredient_score':      ing_score,
            'missing_ingredients':   missing_ings,
            'stew_affordable':       stew_affordable,
            'top_pick':              False,
        })

        if not recently_eaten and ing_score > best_stew_score:
            best_stew_score = ing_score
            top_pick_stew   = s.name.lower()

    # Mark top pick (only when user provided ingredients)
    if top_pick_stew and user_ingredients:
        for sw in stews_with_total:
            if sw['stew'].name.lower() == top_pick_stew and sw['ingredient_score'] == best_stew_score:
                sw['top_pick'] = True
                break

    def stew_sort_key(sw):
        return (
            sw['recently_eaten'],
            not sw['top_pick'],
            -sw['ingredient_score'],
            sw['stew'].name.lower(),
        )

    stews_with_total.sort(key=stew_sort_key)

    available_stews = [
        sw for sw in stews_with_total
        if not sw['recently_eaten'] and sw['stew_affordable']
    ]

    base_recently_eaten = any(
        _text_has_term(base_term, meal.name.lower())
        for base_term, _ in (recent_pairs or [])
    )

    all_stews_excluded = (
        len(all_stews) > 0 and
        len(excluded_stew_names) >= len(all_stews)
    )

    # Is the base meal itself within budget (no stew added)?
    base_within_budget = (budget_int is None) or (meal.total_cost_ksh <= budget_int)

    top_pick_entry = next((sw for sw in stews_with_total if sw['top_pick']), None)

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
        'all_stews':               stews_with_total,
        'available_stews':         available_stews,
        'has_stew_options':        len(all_stews) > 0,
        'excluded_stews':          excluded_stew_names,
        'suggest_other_stews':     base_recently_eaten and not all_stews_excluded and len(excluded_stew_names) > 0,
        'all_stews_excluded':      all_stews_excluded,
        'base_within_budget':      base_within_budget,
        'top_pick_stew':           top_pick_entry,
        'budget_int':              budget_int,
        'user_ingredients':        user_ingredients,
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

        recent_pairs = _parse_recent_pairs(recent_food)

        # -------------------------------------------------------------------
        # SCENARIO 1 — BUDGET ONLY
        # Show all meals whose base cost <= budget.
        # For stew options: mark each stew affordable if base + stew <= budget.
        # base_within_budget = True means the base alone is already within budget.
        # -------------------------------------------------------------------
        if search_mode == 'budget' and budget_int is not None:
            for meal in ComradeMeal.objects.prefetch_related('stew_options').order_by('total_cost_ksh'):
                if meal.total_cost_ksh > budget_int:
                    continue
                if recent_pairs and _should_exclude_meal(meal, recent_pairs):
                    continue
                entry = _build_meal_entry(
                    meal,
                    [],           # no ingredient context in budget-only mode
                    budget_int=budget_int,
                    recent_pairs=recent_pairs,
                )
                entry['tier_label'] = 'budget_only'
                suggested_meals.append(entry)

            affordable_items = ComradeFood.objects.filter(
                price_ksh__lte=budget_int
            ).order_by('price_ksh')

        # -------------------------------------------------------------------
        # SCENARIO 2 — INGREDIENTS ONLY
        # FIX: Only match against the BASE meal text (meal name + shopping items
        # + kitchen items). Stew ingredients are NOT used for the initial filter.
        # This prevents false positives like Ugali appearing when the user has
        # "wheat flour" just because a Ugali stew option contains wheat flour.
        # Stew ingredient scoring still happens inside _build_meal_entry.
        # -------------------------------------------------------------------
        elif search_mode == 'ingredients' and user_ingredients:
            tier1, tier2, tier3 = [], [], []

            for meal in ComradeMeal.objects.prefetch_related('stew_options').all():
                if recent_pairs and _should_exclude_meal(meal, recent_pairs):
                    continue

                # Base text only — no stew text here
                base_text = ' '.join(filter(None, [
                    meal.name,
                    meal.kitchen_items_needed or '',
                    ' '.join(item.get('item', '') for item in (meal.get_items() or [])),
                ])).lower()

                if not any(_text_has_term(ing, base_text) for ing in user_ingredients):
                    continue

                entry = _build_meal_entry(
                    meal,
                    user_ingredients,
                    budget_int=None,
                    recent_pairs=recent_pairs,
                )
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

        # -------------------------------------------------------------------
        # SCENARIO 3 — BOTH (budget + ingredients)
        # Combines budget filtering with ingredient matching.
        # _build_meal_entry uses base text only for match_score, so no
        # cross-flour false positives. Stew affordability is evaluated
        # per stew: base + stew_cost <= budget_int.
        # -------------------------------------------------------------------
        elif search_mode == 'both':
            tier_a, tier_b, tier_c = [], [], []

            for meal in ComradeMeal.objects.prefetch_related('stew_options').all():
                if recent_pairs and _should_exclude_meal(meal, recent_pairs):
                    continue

                entry = _build_meal_entry(
                    meal,
                    user_ingredients,
                    budget_int=budget_int,
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
                    elif adjusted_cost <= budget_int or original_cost <= budget_int:
                        if matched_ings_count > 0:
                            entry['tier_label'] = 'within_budget_match'
                            tier_b.append(entry)
                        else:
                            entry['tier_label'] = 'budget_only'
                            tier_c.append(entry)
                    # Still over budget after savings → skip
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
    """
    Detail page for a ComradeFood item.

    Carries over search context (ingredients, budget, recently eaten) from
    the Low Cost Meals page so we can highlight the top-pick stew and show
    'consider buying' tips for missing stew ingredients.
    """
    food = get_object_or_404(ComradeFood, pk=pk)
    meal = food.meals.prefetch_related('stew_options').first()

    # Carry over search context from query params
    ingredients_input = request.GET.get('ingredients', '').strip()
    budget_param      = request.GET.get('budget', '').strip()
    recent_param      = request.GET.get('recent', '').strip()
    search_mode       = request.GET.get('mode', '')

    user_ingredients = (
        [i.strip().lower() for i in ingredients_input.split(',') if i.strip()]
        if ingredients_input else []
    )
    budget_int = None
    if budget_param:
        try:
            budget_int = int(budget_param)
        except ValueError:
            pass

    recent_pairs = _parse_recent_pairs(recent_param)

    top_pick_stew   = None
    stews_annotated = []

    if meal:
        for stew in meal.stew_options.all():
            ing_score    = _stew_match_score(stew, user_ingredients)
            missing_ings = _stew_missing_ingredients(stew, user_ingredients)
            stew_cost    = float(getattr(stew, 'estimated_cost', 0) or 0)
            total_cost   = meal.total_cost_ksh + stew_cost
            recently_eaten = stew.name.lower() in _get_excluded_stew_names(meal, recent_pairs)
            affordable   = (budget_int is None) or (total_cost <= budget_int)

            stews_annotated.append({
                'stew':                stew,
                'ingredient_score':    ing_score,
                'missing_ingredients': missing_ings,
                'stew_cost':           stew_cost,
                'total_cost':          total_cost,
                'recently_eaten':      recently_eaten,
                'affordable':          affordable,
                'top_pick':            False,
            })

        # Top pick: highest ingredient score, not recently eaten
        if user_ingredients:
            best = max(
                (s for s in stews_annotated if not s['recently_eaten']),
                key=lambda s: s['ingredient_score'],
                default=None,
            )
            if best and best['ingredient_score'] > 0:
                best['top_pick'] = True
                top_pick_stew    = best

    return render(request, 'core/comrade_food_detail.html', {
        'food':               food,
        'meal':               meal,
        # Search context
        'user_ingredients':   user_ingredients,
        'ingredients_input':  ingredients_input,
        'budget_int':         budget_int,
        'budget_param':       budget_param,
        'recent_param':       recent_param,
        'search_mode':        search_mode,
        # Stew context (always populated when meal exists)
        'stews_annotated':    stews_annotated,
        'top_pick_stew':      top_pick_stew,
        'has_search_context': bool(user_ingredients or budget_int),
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