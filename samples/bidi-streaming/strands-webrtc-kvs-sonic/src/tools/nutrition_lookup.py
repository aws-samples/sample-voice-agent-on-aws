"""Nutrition lookup tool using USDA FoodData Central."""

import json
import logging

import requests
from strands import tool

from config import USDA_API_KEY

logger = logging.getLogger(__name__)

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


@tool
def nutrition_lookup(food_item: str) -> str:
    """Look up nutrition information for a food item using USDA FoodData Central.

    Use this when a user asks about calories, macros, or nutrition for a specific
    food item or ingredient.

    Args:
        food_item: The food item to look up, e.g. "chicken breast" or "brown rice"
    """
    try:
        response = requests.get(
            USDA_SEARCH_URL,
            params={
                "query": food_item,
                "pageSize": 1,
                "api_key": USDA_API_KEY,
            },
            timeout=10,
        )

        if not response.ok:
            return f"Could not reach the USDA database. Status: {response.status_code}"

        data = response.json()
        foods = data.get("foods", [])
        if not foods:
            return f"No nutrition data found for '{food_item}'."

        food = foods[0]
        description = food.get("description", food_item)

        # Extract the key nutrients
        target_nutrients = {
            "Energy": "calories",
            "Protein": "protein",
            "Total lipid (fat)": "fat",
            "Carbohydrate, by difference": "carbs",
            "Fiber, total dietary": "fiber",
            "Sugars, total including NLEA": "sugar",
            "Sodium, Na": "sodium",
        }

        nutrients = {}
        for n in food.get("foodNutrients", []):
            name = n.get("nutrientName", "")
            if name in target_nutrients:
                value = n.get("value", 0)
                unit = n.get("unitName", "")
                nutrients[target_nutrients[name]] = f"{value} {unit}".strip()

        if not nutrients:
            return f"Found '{description}' but no nutrient data available."

        result = f"Nutrition for {description} (per 100g serving):\n"
        result += json.dumps(nutrients, indent=2)
        return result

    except requests.Timeout:
        return "USDA API request timed out. Try again."
    except Exception as e:
        logger.exception("Error looking up nutrition")
        return f"Error looking up nutrition: {e}"
