"""LLM service using Google Gemini for intelligent receipt processing."""

import logging
import json
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

class LLMService:
    """Service for using Google Gemini LLM for receipt processing."""

    def __init__(self):
        """Initialize the LLM service."""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        else:
            logger.warning("Gemini API key not configured")
            self.model = None

    def process_receipt_text(self, ocr_text: str, image_path: Optional[str] = None) -> Dict:
        """
        Process receipt text using Gemini to extract structured information.

        Args:
            ocr_text: Raw OCR text from receipt
            image_path: Optional path to receipt image for vision processing

        Returns:
            Dictionary with extracted and categorized information
        """
        if not self.model:
            return self._fallback_processing(ocr_text)

        try:
            prompt = self._create_extraction_prompt(ocr_text)
            response = self.model.generate_content(prompt)

            # Parse the response
            result = self._parse_llm_response(response.text)

            # Validate and clean the result
            result = self._validate_result(result)

            return {
                'success': True,
                'data': result,
                'confidence': result.get('confidence', 0.8)
            }

        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            return self._fallback_processing(ocr_text)

    def categorize_expense(self, receipt_data: Dict) -> str:
        """
        Categorize the expense based on receipt data.

        Args:
            receipt_data: Dictionary with receipt information

        Returns:
            Category name from Config.EXPENSE_CATEGORIES
        """
        if not self.model:
            return self._rule_based_categorization(receipt_data)

        try:
            prompt = self._create_categorization_prompt(receipt_data)
            response = self.model.generate_content(prompt)

            category = response.text.strip()

            # Validate category
            if category in Config.EXPENSE_CATEGORIES:
                return category
            else:
                return self._rule_based_categorization(receipt_data)

        except Exception as e:
            logger.error(f"LLM categorization failed: {e}")
            return self._rule_based_categorization(receipt_data)

    def calculate_tax_deductions(self, receipt_data: Dict) -> Dict:
        """
        Calculate tax deductions based on Dutch tax rules.

        Args:
            receipt_data: Dictionary with receipt information

        Returns:
            Dictionary with tax calculation details
        """
        category = receipt_data.get('category', 'Kantoorkosten')
        total_amount = receipt_data.get('total_amount', 0)
        vat_amount = receipt_data.get('vat_amount', 0)

        # Deduction rules based on category
        deduction_rules = {
            'Beroepskosten': {'vat': 100, 'ib': 100},
            'Kantoorkosten': {'vat': 100, 'ib': 100},
            'Reis- en verblijfkosten': {'vat': 100, 'ib': 100},
            'Representatiekosten - Type 1 (Supermarket)': {'vat': 0, 'ib': 80},
            'Representatiekosten - Type 2 (Horeca)': {'vat': 0, 'ib': 80},
            'Vervoerskosten': {'vat': 100, 'ib': 100},
            'Zakelijke opleidingskosten': {'vat': 100, 'ib': 100}
        }

        rules = deduction_rules.get(category, {'vat': 100, 'ib': 100})

        vat_deductible = vat_amount * (rules['vat'] / 100)
        ib_deductible = (total_amount - vat_amount) * (rules['ib'] / 100)

        return {
            'category': category,
            'vat_deductible_percentage': rules['vat'],
            'ib_deductible_percentage': rules['ib'],
            'vat_deductible_amount': round(vat_deductible, 2),
            'ib_deductible_amount': round(ib_deductible, 2),
            'total_deductible': round(vat_deductible + ib_deductible, 2)
        }

    def _create_extraction_prompt(self, ocr_text: str) -> str:
        """Create prompt for receipt data extraction."""
        return f"""
        Analyze the following receipt text and extract structured information.
        The receipt is likely in Dutch or English.

        Receipt text:
        {ocr_text}

        Extract and return the following information in JSON format:
        {{
            "vendor_name": "Name of the store/vendor",
            "vendor_address": "Address if available",
            "date": "Transaction date in YYYY-MM-DD format",
            "invoice_number": "Receipt/invoice number",
            "items": [
                {{
                    "description": "Item description",
                    "quantity": 1,
                    "unit_price": 0.00,
                    "total_price": 0.00
                }}
            ],
            "subtotal": 0.00,
            "vat_breakdown": {{
                "6": 0.00,
                "9": 0.00,
                "21": 0.00
            }},
            "total_vat": 0.00,
            "total_amount": 0.00,
            "payment_method": "cash/card/unknown",
            "confidence": 0.0 to 1.0,
            "detected_language": "nl/en",
            "notes": "Any additional relevant information"
        }}

        Important:
        - All amounts should be in EUR
        - If information is not found, use null
        - Confidence should reflect how certain you are about the extraction
        - For Dutch receipts, BTW is VAT
        - Common VAT rates in Netherlands: 21% (standard), 9% (reduced), 0% (exempt)
        """

    def _create_categorization_prompt(self, receipt_data: Dict) -> str:
        """Create prompt for expense categorization."""
        categories_str = '\n'.join(f"- {cat}" for cat in Config.EXPENSE_CATEGORIES)

        return f"""
        Based on the following receipt information, determine the most appropriate expense category
        for Dutch freelance tax purposes.

        Receipt Information:
        - Vendor: {receipt_data.get('vendor_name', 'Unknown')}
        - Items: {receipt_data.get('items', [])}
        - Total Amount: €{receipt_data.get('total_amount', 0)}

        Available Categories:
        {categories_str}

        Category Guidelines:
        - Beroepskosten: Professional tools, equipment, software
        - Kantoorkosten: Office supplies, stationery, small office items
        - Reis- en verblijfkosten: Travel and accommodation expenses
        - Representatiekosten - Type 1 (Supermarket): Food/drinks from supermarkets for business
        - Representatiekosten - Type 2 (Horeca): Restaurant/cafe expenses for business
        - Vervoerskosten: Transportation costs (fuel, public transport, parking)
        - Zakelijke opleidingskosten: Professional training and education

        Return ONLY the category name, exactly as listed above.
        """

    def _parse_llm_response(self, response_text: str) -> Dict:
        """Parse LLM response to extract JSON data."""
        try:
            # Try to extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                # If no JSON found, try to parse as plain text
                return self._parse_plain_text_response(response_text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {}

    def _parse_plain_text_response(self, text: str) -> Dict:
        """Parse plain text response when JSON parsing fails."""
        # This is a fallback parser for non-JSON responses
        result = {
            'vendor_name': None,
            'date': None,
            'total_amount': None,
            'vat_breakdown': {'6': 0, '9': 0, '21': 0},
            'items': []
        }

        # Try to extract key information using patterns
        import re

        # Extract vendor (first non-empty line often contains vendor name)
        lines = text.strip().split('\n')
        for line in lines[:5]:
            if line.strip() and len(line.strip()) > 2:
                result['vendor_name'] = line.strip()
                break

        # Extract date
        date_match = re.search(r'\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4}', text)
        if date_match:
            result['date'] = date_match.group()

        # Extract total amount
        amount_match = re.search(r'total.*?(\d+[.,]\d{2})', text.lower())
        if amount_match:
            result['total_amount'] = float(amount_match.group(1).replace(',', '.'))

        return result

    def _validate_result(self, result: Dict) -> Dict:
        """Validate and clean the extracted result."""
        # Ensure all required fields exist
        required_fields = [
            'vendor_name', 'date', 'total_amount', 'vat_breakdown',
            'items', 'confidence'
        ]

        for field in required_fields:
            if field not in result:
                if field == 'items':
                    result[field] = []
                elif field == 'vat_breakdown':
                    result[field] = {'6': 0, '9': 0, '21': 0}
                elif field == 'confidence':
                    result[field] = 0.5
                else:
                    result[field] = None

        # Validate date format
        if result['date']:
            try:
                # Try to parse and reformat date
                from dateutil import parser
                date_obj = parser.parse(result['date'])
                result['date'] = date_obj.strftime('%Y-%m-%d')
            except:
                result['date'] = None

        # Ensure amounts are floats
        if result['total_amount']:
            try:
                result['total_amount'] = float(result['total_amount'])
            except:
                result['total_amount'] = 0.0

        return result

    def _fallback_processing(self, ocr_text: str) -> Dict:
        """Fallback processing when LLM is not available."""
        # Use simple pattern matching as fallback
        from services.ocr_service import OCRService

        structured_data = OCRService.extract_structured_data(ocr_text)

        return {
            'success': True,
            'data': {
                'vendor_name': structured_data.get('vendor_name'),
                'date': structured_data.get('date'),
                'total_amount': structured_data.get('total_amount'),
                'vat_breakdown': structured_data.get('vat_amounts', {}),
                'items': structured_data.get('items', []),
                'invoice_number': structured_data.get('invoice_number'),
                'confidence': 0.5
            },
            'confidence': 0.5
        }

    def _rule_based_categorization(self, receipt_data: Dict) -> str:
        """Rule-based expense categorization as fallback."""
        vendor_name = receipt_data.get('vendor_name', '').lower()

        # Simple rules based on vendor name
        category_rules = {
            'Kantoorkosten': ['office', 'kantoor', 'staples', 'makro', 'viking'],
            'Beroepskosten': ['mediamarkt', 'coolblue', 'bol.com', 'amazon'],
            'Representatiekosten - Type 1 (Supermarket)': ['albert heijn', 'jumbo', 'lidl', 'aldi', 'plus'],
            'Representatiekosten - Type 2 (Horeca)': ['restaurant', 'cafe', 'hotel', 'bar'],
            'Vervoerskosten': ['shell', 'bp', 'esso', 'total', 'ns', 'gvb'],
            'Zakelijke opleidingskosten': ['training', 'course', 'udemy', 'coursera']
        }

        for category, keywords in category_rules.items():
            if any(keyword in vendor_name for keyword in keywords):
                return category

        # Default category
        return 'Kantoorkosten'