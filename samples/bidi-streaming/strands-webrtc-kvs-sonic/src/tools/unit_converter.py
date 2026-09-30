"""Cooking measurement unit converter."""

from strands import tool

# Conversion factors to a common base unit (ml for volume, grams for weight)
_VOLUME_TO_ML = {
    "cup": 236.588,
    "cups": 236.588,
    "tbsp": 14.787,
    "tablespoon": 14.787,
    "tablespoons": 14.787,
    "tsp": 4.929,
    "teaspoon": 4.929,
    "teaspoons": 4.929,
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "fl oz": 29.5735,
    "fluid ounce": 29.5735,
    "fluid ounces": 29.5735,
    "pint": 473.176,
    "pints": 473.176,
    "quart": 946.353,
    "quarts": 946.353,
    "gallon": 3785.41,
    "gallons": 3785.41,
}

_WEIGHT_TO_G = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
}

# Temperature conversion handled separately
_TEMP_UNITS = {"f", "fahrenheit", "c", "celsius"}


def _normalize_unit(unit: str) -> str:
    return unit.lower().strip()


@tool
def convert_units(amount: float, from_unit: str, to_unit: str) -> str:
    """Convert between cooking measurement units.

    Supports volume (cups, tbsp, tsp, ml, liters, fluid ounces, pints, quarts, gallons),
    weight (grams, kg, ounces, pounds), and temperature (Fahrenheit, Celsius).

    Args:
        amount: The numeric amount to convert
        from_unit: The unit to convert from, e.g. "cups", "oz", "fahrenheit"
        to_unit: The unit to convert to, e.g. "ml", "grams", "celsius"
    """
    f = _normalize_unit(from_unit)
    t = _normalize_unit(to_unit)

    # Temperature conversions
    if f in _TEMP_UNITS or t in _TEMP_UNITS:
        if f in ("f", "fahrenheit") and t in ("c", "celsius"):
            result = (amount - 32) * 5 / 9
            return f"{amount} F = {result:.1f} C"
        elif f in ("c", "celsius") and t in ("f", "fahrenheit"):
            result = amount * 9 / 5 + 32
            return f"{amount} C = {result:.1f} F"
        else:
            return (
                f"Cannot convert {from_unit} to {to_unit}. Temperature conversions are between Fahrenheit and Celsius."
            )

    # Volume conversions
    if f in _VOLUME_TO_ML and t in _VOLUME_TO_ML:
        ml = amount * _VOLUME_TO_ML[f]
        result = ml / _VOLUME_TO_ML[t]
        return f"{amount} {from_unit} = {result:.2f} {to_unit}"

    # Weight conversions
    if f in _WEIGHT_TO_G and t in _WEIGHT_TO_G:
        grams = amount * _WEIGHT_TO_G[f]
        result = grams / _WEIGHT_TO_G[t]
        return f"{amount} {from_unit} = {result:.2f} {to_unit}"

    # Check if mixing volume and weight
    if (f in _VOLUME_TO_ML and t in _WEIGHT_TO_G) or (f in _WEIGHT_TO_G and t in _VOLUME_TO_ML):
        return (
            f"Cannot convert {from_unit} to {to_unit} directly. "
            "Volume and weight conversions depend on the density of the ingredient. "
            "For example, 1 cup of flour weighs about 125g, but 1 cup of butter weighs about 227g."
        )

    return f"Unknown unit: '{from_unit}' or '{to_unit}'. I can convert volume, weight, and temperature units."
