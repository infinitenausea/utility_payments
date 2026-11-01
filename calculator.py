from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


TWO_PLACES = Decimal("0.01")
ONE_PLACE = Decimal("0.1")

HOUSE1_NAME = "Настя Толя"
HOUSE2_NAME = "Алёна Айрат"


class CalculationError(ValueError):
    """Ошибка валидации входных данных расчёта."""


def parse_decimal(value: Any, field_name: str, default: Decimal | None = Decimal("0")) -> Decimal:
    """Преобразует входное значение (строку с точкой/запятой или число) в Decimal."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if default is not None:
            return default
        raise CalculationError(f"Заполните поле «{field_name}».")

    raw = (
        str(value)
        .strip()
        .replace("₾", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace(",", ".")
    )
    try:
        num = Decimal(raw)
    except InvalidOperation as exc:
        raise CalculationError(f"Некорректное число в поле «{field_name}»: {value}") from exc

    if not num.is_finite():
        raise CalculationError(f"Некорректное число в поле «{field_name}».")
    if num < 0:
        raise CalculationError(f"Значение в поле «{field_name}» не может быть отрицательным.")

    return num


def round_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def round_reading(value: Decimal) -> str:
    """Форматирует показания и расход без лишних нулей на конце."""
    normalized = value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    text = f"{normalized:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_money(value: Decimal) -> str:
    return f"{round_money(value):.2f}"


def calculate_metered_service(
    label: str,
    unit: str,
    h1_prev: Decimal,
    h1_curr: Decimal,
    h2_prev: Decimal,
    h2_curr: Decimal,
    bill: Decimal,
    house1_name: str,
    house2_name: str,
) -> dict[str, Any]:
    """Считает пропорциональное разделение по показаниям двух счётчиков."""
    if h1_curr < h1_prev:
        raise CalculationError(
            f"{label} ({house1_name}): текущие показания ({round_reading(h1_curr)}) "
            f"меньше прошлых ({round_reading(h1_prev)})."
        )
    if h2_curr < h2_prev:
        raise CalculationError(
            f"{label} ({house2_name}): текущие показания ({round_reading(h2_curr)}) "
            f"меньше прошлых ({round_reading(h2_prev)})."
        )

    diff1 = h1_curr - h1_prev
    diff2 = h2_curr - h2_prev
    total_diff = diff1 + diff2

    note = ""
    if bill == 0:
        cost1 = Decimal("0.00")
        cost2 = Decimal("0.00")
        if total_diff > 0:
            pct1 = (diff1 / total_diff * Decimal("100")).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)
            pct2 = (diff2 / total_diff * Decimal("100")).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)
        else:
            pct1 = Decimal("0.0")
            pct2 = Decimal("0.0")
    elif total_diff == 0:
        # Расход по обоим счётчикам нулевой, но пришёл счёт (например, абонплата)
        cost1 = round_money(bill / Decimal("2"))
        cost2 = round_money(bill / Decimal("2"))
        pct1 = Decimal("50.0")
        pct2 = Decimal("50.0")
        note = "Расход равен 0 — сумма поделена поровну"
    else:
        cost1 = round_money(bill * diff1 / total_diff)
        cost2 = round_money(bill * diff2 / total_diff)
        pct1 = (diff1 / total_diff * Decimal("100")).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)
        pct2 = (diff2 / total_diff * Decimal("100")).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)

    return {
        "label": label,
        "unit": unit,
        "bill": format_money(bill),
        "total_diff": round_reading(total_diff),
        "note": note,
        "house1": {
            "prev": round_reading(h1_prev),
            "curr": round_reading(h1_curr),
            "diff": round_reading(diff1),
            "percent": f"{pct1:.1f}",
            "cost_dec": cost1,
            "cost": format_money(cost1),
        },
        "house2": {
            "prev": round_reading(h2_prev),
            "curr": round_reading(h2_curr),
            "diff": round_reading(diff2),
            "percent": f"{pct2:.1f}",
            "cost_dec": cost2,
            "cost": format_money(cost2),
        },
    }


def calculate_utilities(payload: dict[str, Any]) -> dict[str, Any]:
    """Основная функция расчёта коммунальных платежей для двух домов."""
    house1_name = HOUSE1_NAME
    house2_name = HOUSE2_NAME
    period = str(payload.get("period") or "").strip()

    elec_h1_prev = parse_decimal(payload.get("elec_h1_prev"), f"Свет — {house1_name} (прошлые)")
    elec_h1_curr = parse_decimal(payload.get("elec_h1_curr"), f"Свет — {house1_name} (текущие)")
    elec_h2_prev = parse_decimal(payload.get("elec_h2_prev"), f"Свет — {house2_name} (прошлые)")
    elec_h2_curr = parse_decimal(payload.get("elec_h2_curr"), f"Свет — {house2_name} (текущие)")
    elec_bill = parse_decimal(payload.get("elec_bill"), "Счёт за свет")

    gas_h1_prev = parse_decimal(payload.get("gas_h1_prev"), f"Газ — {house1_name} (прошлые)")
    gas_h1_curr = parse_decimal(payload.get("gas_h1_curr"), f"Газ — {house1_name} (текущие)")
    gas_h2_prev = parse_decimal(payload.get("gas_h2_prev"), f"Газ — {house2_name} (прошлые)")
    gas_h2_curr = parse_decimal(payload.get("gas_h2_curr"), f"Газ — {house2_name} (текущие)")
    gas_bill = parse_decimal(payload.get("gas_bill"), "Счёт за газ")

    water_bill = parse_decimal(payload.get("water_bill"), "Счёт за воду")
    trash_bill = parse_decimal(payload.get("trash_bill"), "Счёт за мусор")

    electricity = calculate_metered_service(
        label="Электричество",
        unit="кВт·ч",
        h1_prev=elec_h1_prev,
        h1_curr=elec_h1_curr,
        h2_prev=elec_h2_prev,
        h2_curr=elec_h2_curr,
        bill=elec_bill,
        house1_name=house1_name,
        house2_name=house2_name,
    )

    gas = calculate_metered_service(
        label="Газ",
        unit="м³",
        h1_prev=gas_h1_prev,
        h1_curr=gas_h1_curr,
        h2_prev=gas_h2_prev,
        h2_curr=gas_h2_curr,
        bill=gas_bill,
        house1_name=house1_name,
        house2_name=house2_name,
    )

    water_half = round_money(water_bill / Decimal("2"))
    trash_half = round_money(trash_bill / Decimal("2"))

    house1_total = (
        electricity["house1"]["cost_dec"]
        + gas["house1"]["cost_dec"]
        + water_half
        + trash_half
    )
    house2_total = (
        electricity["house2"]["cost_dec"]
        + gas["house2"]["cost_dec"]
        + water_half
        + trash_half
    )
    bills_total = round_money(elec_bill + gas_bill + water_bill + trash_bill)
    houses_sum = round_money(house1_total + house2_total)

    # Удаляем внутренние Decimal-поля перед сериализацией в JSON
    del electricity["house1"]["cost_dec"]
    del electricity["house2"]["cost_dec"]
    del gas["house1"]["cost_dec"]
    del gas["house2"]["cost_dec"]

    return {
        "house1_name": house1_name,
        "house2_name": house2_name,
        "period": period,
        "electricity": electricity,
        "gas": gas,
        "water": {
            "label": "Вода",
            "bill": format_money(water_bill),
            "house1_cost": format_money(water_half),
            "house2_cost": format_money(water_half),
        },
        "trash": {
            "label": "Мусор",
            "bill": format_money(trash_bill),
            "house1_cost": format_money(trash_half),
            "house2_cost": format_money(trash_half),
        },
        "totals": {
            "house1": format_money(house1_total),
            "house2": format_money(house2_total),
            "bills_total": format_money(bills_total),
            "houses_sum": format_money(houses_sum),
        },
    }

