"""Calculation utilities for tax and financial computations."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple
from datetime import datetime

from config import Config

def calculate_vat_amount(amount_excl_vat: float, vat_rate: float) -> float:
    """
    Calculate VAT amount from base amount.

    Args:
        amount_excl_vat: Amount excluding VAT
        vat_rate: VAT rate as percentage (e.g., 21 for 21%)

    Returns:
        VAT amount
    """
    vat_decimal = Decimal(str(amount_excl_vat)) * Decimal(str(vat_rate / 100))
    return float(vat_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def calculate_amount_excl_vat(amount_incl_vat: float, vat_rate: float) -> Tuple[float, float]:
    """
    Calculate base amount and VAT from total amount.

    Args:
        amount_incl_vat: Total amount including VAT
        vat_rate: VAT rate as percentage

    Returns:
        Tuple of (amount_excl_vat, vat_amount)
    """
    divisor = Decimal('1') + Decimal(str(vat_rate / 100))
    amount_excl = Decimal(str(amount_incl_vat)) / divisor
    amount_excl = amount_excl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    vat_amount = Decimal(str(amount_incl_vat)) - amount_excl

    return float(amount_excl), float(vat_amount)

def determine_vat_rate(receipt_data: Dict) -> float:
    """
    Determine applicable VAT rate based on receipt data.

    Args:
        receipt_data: Dictionary with receipt information

    Returns:
        VAT rate as percentage
    """
    # Check for explicit VAT rate in data
    if 'vat_rate' in receipt_data:
        return receipt_data['vat_rate']

    # Check VAT breakdown
    vat_breakdown = receipt_data.get('vat_breakdown', {})

    if vat_breakdown.get('21', 0) > 0:
        return 21.0
    elif vat_breakdown.get('9', 0) > 0:
        return 9.0
    elif vat_breakdown.get('6', 0) > 0:
        return 9.0  # 6% rate changed to 9% in 2024
    else:
        # Default to standard rate
        return 21.0

def calculate_tax_deductions(
    category: str,
    amount_excl_vat: float,
    vat_amount: float,
    custom_percentages: Dict = None
) -> Dict:
    """
    Calculate tax deductions based on category and Dutch tax rules.

    Args:
        category: Expense category
        amount_excl_vat: Amount excluding VAT
        vat_amount: VAT amount
        custom_percentages: Optional custom deduction percentages

    Returns:
        Dictionary with deduction calculations
    """
    # Default deduction rules
    default_rules = {
        'Beroepskosten': {'vat': 100, 'ib': 100},
        'Kantoorkosten': {'vat': 100, 'ib': 100},
        'Reis- en verblijfkosten': {'vat': 100, 'ib': 100},
        'Representatiekosten - Type 1 (Supermarket)': {'vat': 0, 'ib': 80},
        'Representatiekosten - Type 2 (Horeca)': {'vat': 0, 'ib': 80},
        'Vervoerskosten': {'vat': 100, 'ib': 100},
        'Zakelijke opleidingskosten': {'vat': 100, 'ib': 100}
    }

    # Use custom percentages if provided, otherwise use defaults
    if custom_percentages and category in custom_percentages:
        rules = custom_percentages[category]
    else:
        rules = default_rules.get(category, {'vat': 100, 'ib': 100})

    # Calculate deductible amounts
    vat_deductible = vat_amount * (rules['vat'] / 100)
    ib_deductible = amount_excl_vat * (rules['ib'] / 100)

    # Calculate remainder after VAT refund
    remainder_after_vat = amount_excl_vat + vat_amount - vat_deductible

    # Calculate profit deduction (winstaftrek)
    profit_deduction = remainder_after_vat * (rules['ib'] / 100)

    return {
        'vat_deductible_percentage': rules['vat'],
        'ib_deductible_percentage': rules['ib'],
        'vat_deductible_amount': round(vat_deductible, 2),
        'ib_deductible_amount': round(ib_deductible, 2),
        'remainder_after_vat': round(remainder_after_vat, 2),
        'profit_deduction': round(profit_deduction, 2),
        'total_deductible': round(vat_deductible + profit_deduction, 2),
        'net_cost': round(amount_excl_vat + vat_amount - vat_deductible - profit_deduction, 2)
    }

def calculate_quarterly_vat(receipts: List[Dict]) -> Dict:
    """
    Calculate quarterly VAT summary for tax declaration.

    Args:
        receipts: List of receipt dictionaries

    Returns:
        Dictionary with quarterly VAT calculations
    """
    summary = {
        'total_sales': 0,
        'vat_on_sales': 0,
        'total_purchases': 0,
        'vat_on_purchases': {
            '6': 0,
            '9': 0,
            '21': 0,
            'total': 0
        },
        'deductible_vat': 0,
        'non_deductible_vat': 0,
        'vat_balance': 0,  # To pay or refund
        'receipt_count': len(receipts)
    }

    for receipt in receipts:
        # Add purchase amounts
        amount_excl = receipt.get('amount_excl_vat', 0)
        summary['total_purchases'] += amount_excl

        # Add VAT amounts by rate
        vat_breakdown = receipt.get('vat_breakdown', {})
        for rate, amount in vat_breakdown.items():
            if rate in summary['vat_on_purchases']:
                summary['vat_on_purchases'][rate] += amount
                summary['vat_on_purchases']['total'] += amount

        # Calculate deductible VAT
        category = receipt.get('category', 'Kantoorkosten')
        deductions = calculate_tax_deductions(
            category,
            amount_excl,
            sum(vat_breakdown.values())
        )

        summary['deductible_vat'] += deductions['vat_deductible_amount']
        summary['non_deductible_vat'] += (
            sum(vat_breakdown.values()) - deductions['vat_deductible_amount']
        )

    # Calculate VAT balance (negative = refund, positive = to pay)
    summary['vat_balance'] = summary['vat_on_sales'] - summary['deductible_vat']

    # Round all values
    for key in summary:
        if isinstance(summary[key], float):
            summary[key] = round(summary[key], 2)
        elif isinstance(summary[key], dict):
            for subkey in summary[key]:
                if isinstance(summary[key][subkey], float):
                    summary[key][subkey] = round(summary[key][subkey], 2)

    return summary

def calculate_annual_summary(receipts: List[Dict]) -> Dict:
    """
    Calculate annual summary for income tax purposes.

    Args:
        receipts: List of receipt dictionaries

    Returns:
        Dictionary with annual summary
    """
    summary = {
        'total_expenses': 0,
        'total_vat_paid': 0,
        'total_vat_refunded': 0,
        'by_category': {},
        'by_month': {},
        'deductible_expenses': 0,
        'non_deductible_expenses': 0,
        'receipt_count': len(receipts)
    }

    # Initialize category totals
    for category in Config.EXPENSE_CATEGORIES:
        summary['by_category'][category] = {
            'count': 0,
            'amount_excl_vat': 0,
            'vat': 0,
            'total': 0,
            'deductible': 0
        }

    # Process each receipt
    for receipt in receipts:
        amount_excl = receipt.get('amount_excl_vat', 0)
        vat_amount = sum(receipt.get('vat_breakdown', {}).values())
        total_amount = amount_excl + vat_amount
        category = receipt.get('category', 'Kantoorkosten')

        # Update totals
        summary['total_expenses'] += total_amount
        summary['total_vat_paid'] += vat_amount

        # Update category totals
        if category in summary['by_category']:
            summary['by_category'][category]['count'] += 1
            summary['by_category'][category]['amount_excl_vat'] += amount_excl
            summary['by_category'][category]['vat'] += vat_amount
            summary['by_category'][category]['total'] += total_amount

        # Calculate deductions
        deductions = calculate_tax_deductions(category, amount_excl, vat_amount)

        summary['total_vat_refunded'] += deductions['vat_deductible_amount']
        summary['deductible_expenses'] += deductions['profit_deduction']
        summary['non_deductible_expenses'] += (
            amount_excl - deductions['profit_deduction']
        )

        if category in summary['by_category']:
            summary['by_category'][category]['deductible'] += deductions['profit_deduction']

        # Update monthly totals
        receipt_date = receipt.get('date')
        if receipt_date:
            if isinstance(receipt_date, str):
                receipt_date = datetime.strptime(receipt_date, '%Y-%m-%d')

            month_key = receipt_date.strftime('%Y-%m')

            if month_key not in summary['by_month']:
                summary['by_month'][month_key] = {
                    'count': 0,
                    'total': 0,
                    'vat': 0,
                    'deductible': 0
                }

            summary['by_month'][month_key]['count'] += 1
            summary['by_month'][month_key]['total'] += total_amount
            summary['by_month'][month_key]['vat'] += vat_amount
            summary['by_month'][month_key]['deductible'] += deductions['profit_deduction']

    # Round all values
    summary = round_nested_dict(summary)

    return summary

def calculate_vat_summary(receipts: List[Dict]) -> Dict:
    """
    Calculate VAT summary for display.

    Args:
        receipts: List of receipt dictionaries

    Returns:
        Dictionary with VAT summary
    """
    summary = {
        'vat_6': 0,
        'vat_9': 0,
        'vat_21': 0,
        'total_vat': 0,
        'deductible_vat': 0,
        'non_deductible_vat': 0,
        'effective_rate': 0
    }

    total_amount = 0

    for receipt in receipts:
        vat_breakdown = receipt.get('vat_breakdown', {})

        summary['vat_6'] += vat_breakdown.get('6', 0)
        summary['vat_9'] += vat_breakdown.get('9', 0)
        summary['vat_21'] += vat_breakdown.get('21', 0)

        total_vat = sum(vat_breakdown.values())
        summary['total_vat'] += total_vat

        # Calculate deductible portion
        category = receipt.get('category', 'Kantoorkosten')
        amount_excl = receipt.get('amount_excl_vat', 0)
        deductions = calculate_tax_deductions(category, amount_excl, total_vat)

        summary['deductible_vat'] += deductions['vat_deductible_amount']
        summary['non_deductible_vat'] += total_vat - deductions['vat_deductible_amount']

        total_amount += amount_excl + total_vat

    # Calculate effective VAT rate
    if total_amount > 0:
        summary['effective_rate'] = (summary['total_vat'] / total_amount) * 100

    # Round all values
    for key in summary:
        if isinstance(summary[key], float):
            summary[key] = round(summary[key], 2)

    return summary

def calculate_expense_summary(receipts: List[Dict]) -> Dict:
    """
    Calculate expense summary by category.

    Args:
        receipts: List of receipt dictionaries

    Returns:
        Dictionary with expense summary
    """
    summary = {}

    for category in Config.EXPENSE_CATEGORIES:
        summary[category] = {
            'count': 0,
            'total': 0,
            'average': 0,
            'percentage': 0
        }

    total_amount = 0

    for receipt in receipts:
        category = receipt.get('category', 'Kantoorkosten')
        amount = (
            receipt.get('amount_excl_vat', 0) +
            sum(receipt.get('vat_breakdown', {}).values())
        )

        if category in summary:
            summary[category]['count'] += 1
            summary[category]['total'] += amount
            total_amount += amount

    # Calculate averages and percentages
    for category in summary:
        if summary[category]['count'] > 0:
            summary[category]['average'] = (
                summary[category]['total'] / summary[category]['count']
            )

        if total_amount > 0:
            summary[category]['percentage'] = (
                summary[category]['total'] / total_amount * 100
            )

        # Round values
        summary[category]['total'] = round(summary[category]['total'], 2)
        summary[category]['average'] = round(summary[category]['average'], 2)
        summary[category]['percentage'] = round(summary[category]['percentage'], 1)

    return summary

def round_nested_dict(d: Dict, decimals: int = 2) -> Dict:
    """
    Recursively round all float values in a nested dictionary.

    Args:
        d: Dictionary to round
        decimals: Number of decimal places

    Returns:
        Dictionary with rounded values
    """
    for key, value in d.items():
        if isinstance(value, float):
            d[key] = round(value, decimals)
        elif isinstance(value, dict):
            d[key] = round_nested_dict(value, decimals)

    return d