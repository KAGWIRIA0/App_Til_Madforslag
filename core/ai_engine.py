from google import genai
from google.genai import types
from decouple import config
import time

client = genai.Client(api_key=config('GEMINI_API_KEY'))

MODEL = 'gemini-2.0-flash'


def suggest_meals_from_ingredients(ingredients: list) -> str:
    ingredients_text = ', '.join(ingredients)

    prompt = f"""
You are a Kenyan food assistant for DishCraft, an all user meal app.

The user has these ingredients: {ingredients_text}

Suggest 3 Kenyan meals they can make. For each meal:
1. Meal name
2. Which of their ingredients it uses
3. What extra cheap items to buy (with Kenyan Shilling prices)
4. Estimated total cost in Ksh

Keep suggestions affordable, under Ksh 150.
Be specific to Kenyan cuisine (ugali, chapati, sukuma etc).
"""
    
    for attempt in range(2):  # try twice
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt
            )
            return response.text
        except Exception as e:
            if '429' in str(e) and attempt == 0:
                time.sleep(3)  # wait 3 seconds then retry once
                continue
            raise


def suggest_meals_from_image(image_bytes: bytes) -> str:
    import PIL.Image
    import io

    image = PIL.Image.open(io.BytesIO(image_bytes))

    prompt = """
You are a Kenyan food assistant for DishCraft.

Look at the ingredients in this photo.
1. List what ingredients you can see
2. Suggest 3 affordable Kenyan meals using them
3. For each meal, list any cheap extras to buy (in Ksh)
4. Estimate total cost in Ksh

Focus on student-friendly, affordable Kenyan meals.
"""

    for attempt in range(2):  # try twice
        try:
            response = client.models.generate_content(                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      
                model=MODEL,
                contents=[prompt, image]
            )
            return response.text
        except Exception as e:
            if '429' in str(e) and attempt == 0:
                time.sleep(3)  # wait 3 seconds then retry once
                continue
            raise

def suggest_from_voice(transcript: str) -> str:
    prompt = f"""
You are a Kenyan food assistant for DishCraft.

A user said: "{transcript}"

Extract the ingredients they mentioned and suggest 3 affordable
Kenyan meals. For each meal:
1. Meal name
2. Ingredients they already have that match
3. Cheap extras to buy (with Ksh prices)
4. Total estimated cost in Ksh

Keep it simple, practical and student-budget friendly.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )
    return response.text