"""LLM service using ONLY Google Gemini Vision for receipt processing."""

import logging
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import google.generativeai as genai
from PIL import Image
import PyPDF2
import io

from config import Config

logger = logging.getLogger(__name__)

class LLMService:
    """Service for using Google Gemini Vision for receipt processing."""

    def __init__(self):
        """Initialize the LLM service."""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            # Use Gemini 2.5 Flash Lite for vision processing
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        else:
            logger.warning("Gemini API key not configured")
            self.model = None

    def process_receipt_file(self, file_path: str) -> Dict:
        """
        Process receipt file (PDF or image) directly with Gemini Vision.

        Args:
            file_path: Path to receipt file (PDF, PNG, JPG, JPEG)

        Returns:
            Dictionary with extracted and categorized information
        """
        if not self.model:
            return {
                'success': False,
                'error': 'Gemini API not configured'
            }

        try:
            file_path_obj = Path(file_path)

            # Load file based on type
            if file_path.lower().endswith('.pdf'):
                # For PDF, convert first page to image
                image = self._pdf_to_image(file_path)
            else:
                # For images, load directly
                image = Image.open(file_path)

            # Create comprehensive extraction prompt
            prompt = self._create_vision_extraction_prompt()

            # Process with Gemini Vision
            response = self.model.generate_content([prompt, image])

            # Parse the response
            result = self._parse_llm_response(response.text)

            # Add category
            result['category'] = self.categorize_from_data(result)

            # Calculate tax deductions
            tax_info = self.calculate_tax_deductions(result)
            result.update(tax_info)

            return {
                'success': True,
                'data': result,
                'confidence': result.get('confidence', 0.8),
                'raw_response': response.text
            }

        except Exception as e:
            logger.error(f"Gemini Vision processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _pdf_to_image(self, pdf_path: str) -> Image.Image:
        """Convert first page of PDF to image."""
        try:
            # First try to extract text and create image from it
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if len(pdf_reader.pages) > 0:
                    # For now, try pdf2image if available, otherwise use text extraction
                    try:
                        from pdf2image import convert_from_path
                        images = convert_from_path(pdf_path, first_page=1, last_page=1)
                        return images[0]
                    except:
                        # Fallback: create a simple image with the PDF text
                        page_text = pdf_reader.pages[0].extract_text()
                        # Create a white image with text
                        from PIL import ImageDraw, ImageFont
                        img = Image.new('RGB', (800, 1000), color='white')
                        draw = ImageDraw.Draw(img)
                        draw.text((10, 10), page_text[:500], fill='black')
                        return img
        except Exception as e:
            logger.error(f"PDF conversion error: {e}")
            # Return blank image as fallback
            return Image.new('RGB', (800, 1000), color='white')

    def _create_vision_extraction_prompt(self) -> str:
        """Create comprehensive prompt for Gemini Vision."""
        categories_str = '\n'.join(f"        - {cat}" for cat in Config.EXPENSE_CATEGORIES)

        return f"""
Analyze this receipt image and extract ALL information in JSON format.

Extract the following details:

{{
    "vendor_name": "Store/company name",
    "vendor_address": "Full address if visible",
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
- VAT rates in Netherlands: 21% (hoog/standard), 9% (laag/reduced), 0% (geen)
- Extract EXACT amounts from the receipt
- If unsure about a value, set confidence lower
- Date format must be YYYY-MM-DD (convert DD-MM-YYYY if needed)
- Calculate totals if not clearly shown

Return ONLY valid JSON, no additional text.
"""

    def categorize_from_data(self, receipt_data: Dict) -> str:
        """
        Categorize expense based on vendor and items.

        Args:
            receipt_data: Extracted receipt data

        Returns:
            Category name
        """
        vendor = (receipt_data.get('vendor_name', '') or '').lower()
        items = receipt_data.get('items', [])

        # Simple rule-based categorization
        if any(name in vendor for name in ['albert heijn', 'jumbo', 'lidl', 'aldi', 'plus']):
            return 'Representatiekosten - Type 1 (Supermarket)'
        elif any(name in vendor for name in ['restaurant', 'cafe', 'coffee', 'koffie']):
            return 'Representatiekosten - Type 2 (Horeca)'
        elif any(name in vendor for name in ['shell', 'esso', 'bp', 'tank']):
            return 'Vervoerskosten'
        elif any(name in vendor for name in ['staples', 'office', 'kantoor']):
            return 'Kantoorkosten'
        elif any(name in vendor for name in ['bol.com', 'coolblue', 'mediamarkt']):
            return 'Beroepskosten'
        else:
            return 'Kantoorkosten'  # Default

    def calculate_tax_deductions(self, receipt_data: Dict) -> Dict:
        """
        Calculate tax deductions based on Dutch tax rules.

        Args:
            receipt_data: Dictionary with receipt information

        Returns:
            Dictionary with tax calculation details
        """
        category = receipt_data.get('category', 'Kantoorkosten')
        total_amount = float(receipt_data.get('total_amount', 0))
        vat_breakdown = receipt_data.get('vat_breakdown', {})

        # Calculate total VAT
        total_vat = sum(float(v) for v in vat_breakdown.values())
        amount_excl_vat = total_amount - total_vat

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

        vat_deductible = total_vat * (rules['vat'] / 100)
        ib_deductible = amount_excl_vat * (rules['ib'] / 100)
        remainder_after_vat = total_amount - vat_deductible
        profit_deduction = ib_deductible

        return {
            'amount_excl_vat': round(amount_excl_vat, 2),
            'vat_amount': round(total_vat, 2),
            'vat_deductible_percentage': rules['vat'],
            'ib_deductible_percentage': rules['ib'],
            'vat_deductible_amount': round(vat_deductible, 2),
            'remainder_after_vat': round(remainder_after_vat, 2),
            'profit_deduction': round(profit_deduction, 2)
        }

    def _parse_llm_response(self, response_text: str) -> Dict:
        """Parse JSON response from Gemini."""
        try:
            # Try to find JSON in the response
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])

            # Remove any text before first { and after last }
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end > start:
                response_text = response_text[start:end]

            data = json.loads(response_text)
            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {response_text}")
            # Return minimal valid data
            return {
                'vendor_name': 'Unknown',
                'date': None,
                'total_amount': 0,
                'vat_breakdown': {'6': 0, '9': 0, '21': 0},
                'confidence': 0.3,
                'notes': f'Parse error: {str(e)}'
            }
