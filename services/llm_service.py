"""LLM service with 3-step Gemini processing pipeline."""

import logging
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import google.generativeai as genai
from PIL import Image
import PyPDF2

from config import Config
from utils.database_utils import get_category_tax_rules, ensure_user_settings_exists

logger = logging.getLogger(__name__)

class LLMService:
    """Service for 3-step Gemini processing: Image→Text→Structured Data→Category."""

    def __init__(self):
        """Initialize the LLM service."""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        else:
            logger.warning("Gemini API key not configured")
            self.model = None

    def process_receipt_file(self, file_path: str) -> Dict:
        """
        Process receipt file using 3-step Gemini pipeline.

        Step 1: Image → Raw Text
        Step 2: Raw Text → Structured Data
        Step 3: Structured Data → Category
        Step 4: Python rules → BTW/IB percentages

        Args:
            file_path: Path to receipt file (PDF, PNG, JPG, JPEG)

        Returns:
            Dictionary with extracted data and raw text
        """
        if not self.model:
            return {
                'success': False,
                'error': 'Gemini API not configured'
            }

        try:
            # STEP 1: Get raw text
            # For PDFs (digital receipts): extract text directly from PDF
            # For images (physical receipts): use Gemini Vision
            if file_path.lower().endswith('.pdf'):
                logger.info("Step 1: Extracting raw text directly from PDF (digital receipt)")
                raw_text = self._extract_text_from_pdf(file_path)
            else:
                logger.info("Step 1: Extracting raw text from physical receipt image with Gemini")
                image = Image.open(file_path)
                raw_text = self._extract_raw_text(image)

            # STEP 2: Raw Text to Structured Data
            logger.info("Step 2: Converting raw text to structured data with Gemini")
            structured_data = self._text_to_structured_data(raw_text)

            # STEP 3: Extract Category
            logger.info("Step 3: Extracting category from structured data with Gemini")
            category = self._extract_category(structured_data)
            structured_data['category'] = category

            # STEP 4: Apply rule-based BTW/IB percentages
            logger.info("Step 4: Applying Dutch tax rules (BTW/IB aftrekbaar)")
            tax_percentages = self._apply_tax_rules(category)
            structured_data.update(tax_percentages)

            # Calculate amounts
            tax_calculations = self._calculate_tax_amounts(structured_data)
            structured_data.update(tax_calculations)

            return {
                'success': True,
                'data': structured_data,
                'raw_text': raw_text,  # Step 1 output
                'structured_data_json': json.dumps(structured_data, indent=2, ensure_ascii=False),  # Step 2 output
                'extracted_category': category,  # Step 3 output
                'confidence': structured_data.get('confidence', 0.8)
            }

        except Exception as e:
            logger.error(f"Gemini processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _extract_raw_text(self, image: Image.Image) -> str:
        """
        STEP 1: Extract raw text from image using Gemini Vision.

        Args:
            image: PIL Image

        Returns:
            Raw text extracted from receipt
        """
        prompt = """
Extract ALL text from this receipt image exactly as it appears.
Do not analyze or structure the data - just extract the raw text.
Include:
- Store name
- Address
- All items
- Prices
- Dates
- Invoice/receipt numbers
- VAT information
- Totals
- Payment information

Return only the raw text, line by line as it appears on the receipt.
"""
        response = self.model.generate_content([prompt, image])
        return response.text

    def _text_to_structured_data(self, raw_text: str) -> Dict:
        """
        STEP 2: Convert raw text to structured data using Gemini.

        Args:
            raw_text: Raw text from receipt

        Returns:
            Structured data dictionary
        """
        prompt = f"""
Analyze this receipt text and extract structured information.

Receipt text:
{raw_text}

Extract and return the following information in JSON format:
{{
    "vendor_name": "Store/company name",
    "vendor_address": "Full address",
    "date": "Transaction date in YYYY-MM-DD format",
    "invoice_number": "Receipt/invoice number",
    "items": [
        {{
            "description": "Item name",
            "quantity": 1,
            "unit_price": 0.00,
            "total_price": 0.00,
            "vat_rate": 21
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
    "payment_method": "cash/card/pin/unknown",
    "confidence": 0.95,
    "detected_language": "nl or en",
    "notes": "Any relevant information"
}}

IMPORTANT RULES:
- All amounts in EUR (€)
- For Dutch receipts: "BTW" = VAT, "Totaal" = Total
- VAT rates in Netherlands: 21% (hoog), 9% (laag), 6% (old rate), 0% (geen)
- Extract EXACT amounts from the receipt
- Date format must be YYYY-MM-DD
- If unsure about a value, set confidence lower

Return ONLY valid JSON, no additional text.
"""
        response = self.model.generate_content(prompt)
        return self._parse_json_response(response.text)

    def _extract_category(self, structured_data: Dict) -> str:
        """
        STEP 3: Extract expense category using Gemini.

        Args:
            structured_data: Structured receipt data

        Returns:
            Category name from predefined list
        """
        categories = [
            "Beroepskosten",
            "Kantoorkosten",
            "Reis- en verblijfkosten",
            "Representatiekosten - Type 1 (Supermarket)",
            "Representatiekosten - Type 2 (Horeca)",
            "Vervoerskosten",
            "Zakelijke opleidingskosten"
        ]

        categories_str = '\n'.join(f"  {i+1}. {cat}" for i, cat in enumerate(categories))

        prompt = f"""
Based on this receipt information, determine the expense category for Dutch freelance tax purposes.

Receipt Data:
- Vendor: {structured_data.get('vendor_name', 'Unknown')}
- Items: {json.dumps(structured_data.get('items', []), ensure_ascii=False)}
- Total: €{structured_data.get('total_amount', 0)}

Available Categories:
{categories_str}

Category Guidelines:
1. Beroepskosten: Professional tools, equipment, software, electronics for work
2. Kantoorkosten: Office supplies, stationery, small office items
3. Reis- en verblijfkosten: Travel expenses, accommodation, hotels
4. Representatiekosten - Type 1 (Supermarket): Food/drinks from supermarkets (Albert Heijn, Jumbo, Lidl, etc.)
5. Representatiekosten - Type 2 (Horeca): Restaurant, cafe, bar expenses
6. Vervoerskosten: Fuel, parking, public transport, taxi
7. Zakelijke opleidingskosten: Training courses, books, educational materials

Return ONLY the category name exactly as listed above, nothing else.
"""
        response = self.model.generate_content(prompt)
        category = response.text.strip()

        # Validate category
        if category not in categories:
            logger.warning(f"Invalid category '{category}', defaulting to Kantoorkosten")
            return "Kantoorkosten"

        return category

    def _apply_tax_rules(self, category: str) -> Dict:
        """
        STEP 4: Apply rule-based Dutch tax deduction rules FROM DATABASE.
        This reads the tax percentages from the Instellingen page (BTW & Belasting tab).

        Args:
            category: Expense category

        Returns:
            Dictionary with BTW and IB aftrekbaar percentages
        """
        # Get user settings ID
        user_settings_id = ensure_user_settings_exists(user_id=1)

        # Get tax rules from database
        tax_rules_db = get_category_tax_rules(user_settings_id)

        # Default fallback values if database is empty
        default_tax_rules = {
            'Beroepskosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
            'Kantoorkosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
            'Reis- en verblijfkosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
            'Representatiekosten - Type 1 (Supermarket)': {'btw_aftrekbaar': 0, 'ib_aftrekbaar': 80},
            'Representatiekosten - Type 2 (Horeca)': {'btw_aftrekbaar': 0, 'ib_aftrekbaar': 80},
            'Vervoerskosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
            'Zakelijke opleidingskosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100}
        }

        # Use database rules if available, otherwise use defaults
        if category in tax_rules_db:
            btw_aftrekbaar = tax_rules_db[category]['vat_deductible']
            ib_aftrekbaar = tax_rules_db[category]['ib_deductible']
            logger.info(f"Using database tax rules for {category}: BTW {btw_aftrekbaar}%, IB {ib_aftrekbaar}%")
        else:
            default_rule = default_tax_rules.get(category, {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100})
            btw_aftrekbaar = default_rule['btw_aftrekbaar']
            ib_aftrekbaar = default_rule['ib_aftrekbaar']
            logger.info(f"Using default tax rules for {category}: BTW {btw_aftrekbaar}%, IB {ib_aftrekbaar}%")

        return {
            'vat_deductible_percentage': btw_aftrekbaar,
            'ib_deductible_percentage': ib_aftrekbaar
        }

    def _calculate_tax_amounts(self, structured_data: Dict) -> Dict:
        """
        Calculate actual tax amounts based on percentages.

        Args:
            structured_data: Receipt data with percentages

        Returns:
            Calculated tax amounts
        """
        total_amount = float(structured_data.get('total_amount', 0))
        vat_breakdown = structured_data.get('vat_breakdown', {})
        total_vat = sum(float(v) for v in vat_breakdown.values())
        amount_excl_vat = total_amount - total_vat

        btw_percentage = structured_data.get('vat_deductible_percentage', 100)
        ib_percentage = structured_data.get('ib_deductible_percentage', 100)

        vat_deductible = total_vat * (btw_percentage / 100)
        remainder_after_vat = total_amount - vat_deductible
        profit_deduction = amount_excl_vat * (ib_percentage / 100)

        return {
            'amount_excl_vat': round(amount_excl_vat, 2),
            'vat_amount': round(total_vat, 2),
            'vat_deductible_amount': round(vat_deductible, 2),
            'remainder_after_vat': round(remainder_after_vat, 2),
            'profit_deduction': round(profit_deduction, 2)
        }

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text directly from PDF (for digital receipts).
        No image conversion needed - PDFs already contain text.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Raw text extracted from PDF
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                # Extract text from all pages
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""

    def _parse_json_response(self, response_text: str) -> Dict:
        """Parse JSON response from Gemini."""
        try:
            # Remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
                if response_text.startswith('json'):
                    response_text = response_text[4:]

            # Find JSON in response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                response_text = response_text[start:end]

            data = json.loads(response_text)
            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {response_text}")
            return {
                'vendor_name': 'Unknown',
                'date': None,
                'total_amount': 0,
                'vat_breakdown': {'6': 0, '9': 0, '21': 0},
                'confidence': 0.3,
                'notes': f'Parse error: {str(e)}'
            }
