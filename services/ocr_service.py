"""OCR service for extracting text from receipts."""

import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import re
from PIL import Image
import pytesseract
import cv2
import numpy as np

from config import Config

logger = logging.getLogger(__name__)

class OCRService:
    """Service for performing OCR on receipt images."""

    SUPPORTED_LANGUAGES = ['nld', 'eng']  # Dutch and English

    @classmethod
    def process_receipt(cls, file_path: str) -> Dict:
        """
        Process a receipt file and extract text using OCR.

        Args:
            file_path: Path to the receipt file

        Returns:
            Dictionary containing OCR results
        """
        try:
            # Handle PDFs differently - extract text directly
            if file_path.lower().endswith('.pdf'):
                ocr_text = cls.extract_text_from_pdf(file_path)
                if not ocr_text or len(ocr_text.strip()) < 10:
                    return {
                        'success': False,
                        'error': 'PDF text extraction failed or no text found',
                        'file_path': file_path
                    }
            else:
                # Preprocess image
                processed_image = cls.preprocess_image(file_path)

                # Perform OCR
                ocr_text = cls.extract_text(processed_image)

            # Detect language
            language = cls.detect_language(ocr_text)

            # Extract structured data
            structured_data = cls.extract_structured_data(ocr_text)

            # Calculate confidence score
            confidence = cls.calculate_confidence(ocr_text)

            return {
                'success': True,
                'raw_text': ocr_text,
                'language': language,
                'confidence': confidence,
                'structured_data': structured_data,
                'file_path': file_path
            }

        except Exception as e:
            logger.error(f"OCR processing failed for {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'file_path': file_path
            }

    @classmethod
    def extract_text_from_pdf(cls, file_path: str) -> str:
        """
        Extract text directly from PDF using PyPDF2.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text
        """
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""

    @classmethod
    def preprocess_image(cls, file_path: str) -> np.ndarray:
        """
        Preprocess image for better OCR results.

        Args:
            file_path: Path to the image file

        Returns:
            Preprocessed image as numpy array
        """
        # Read image (skip for PDFs - we'll extract text directly)
        if file_path.lower().endswith('.pdf'):
            # For PDFs, return empty array - we'll use direct text extraction
            return np.array([])
        else:
            image = cv2.imread(file_path)

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply thresholding to get better OCR results
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Denoise
        denoised = cv2.medianBlur(thresh, 1)

        # Deskew image
        deskewed = cls.deskew_image(denoised)

        return deskewed

    @classmethod
    def deskew_image(cls, image: np.ndarray) -> np.ndarray:
        """
        Deskew an image to improve OCR accuracy.

        Args:
            image: Input image

        Returns:
            Deskewed image
        """
        # Find all white pixels
        coords = np.column_stack(np.where(image > 0))

        # Calculate the skew angle
        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Rotate the image to deskew it
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

        return rotated

    @classmethod
    def extract_text(cls, image: np.ndarray) -> str:
        """
        Extract text from image using Tesseract OCR.

        Args:
            image: Preprocessed image

        Returns:
            Extracted text
        """
        # Configure Tesseract
        custom_config = r'--oem 3 --psm 6'

        # Perform OCR for Dutch and English
        try:
            text = pytesseract.image_to_string(
                image,
                lang='nld+eng',
                config=custom_config
            )
        except Exception as e:
            logger.warning(f"OCR with Dutch failed, trying English only: {e}")
            text = pytesseract.image_to_string(
                image,
                lang='eng',
                config=custom_config
            )

        return text

    @classmethod
    def detect_language(cls, text: str) -> str:
        """
        Detect the language of the text.

        Args:
            text: OCR extracted text

        Returns:
            Detected language code ('nl' or 'en')
        """
        # Simple Dutch detection based on common words
        dutch_indicators = [
            'btw', 'totaal', 'bedrag', 'datum', 'bon', 'kassabon',
            'inclusief', 'exclusief', 'aantal', 'prijs', 'korting',
            'subtotaal', 'te betalen', 'contant', 'pinnen', 'retour'
        ]

        text_lower = text.lower()
        dutch_count = sum(1 for word in dutch_indicators if word in text_lower)

        return 'nl' if dutch_count >= 3 else 'en'

    @classmethod
    def extract_structured_data(cls, text: str) -> Dict:
        """
        Extract structured data from OCR text.

        Args:
            text: OCR extracted text

        Returns:
            Dictionary with extracted structured data
        """
        data = {
            'date': cls.extract_date(text),
            'total_amount': cls.extract_total_amount(text),
            'vat_amounts': cls.extract_vat_amounts(text),
            'vendor_name': cls.extract_vendor_name(text),
            'invoice_number': cls.extract_invoice_number(text),
            'items': cls.extract_line_items(text)
        }

        return data

    @classmethod
    def extract_date(cls, text: str) -> Optional[str]:
        """Extract date from text."""
        # Common date patterns
        date_patterns = [
            r'\d{2}[-/]\d{2}[-/]\d{4}',  # DD-MM-YYYY or DD/MM/YYYY
            r'\d{4}[-/]\d{2}[-/]\d{2}',  # YYYY-MM-DD or YYYY/MM/DD
            r'\d{2}-\d{2}-\d{2}',         # DD-MM-YY
            r'\d{1,2}\s+\w+\s+\d{4}',     # D Month YYYY
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    @classmethod
    def extract_total_amount(cls, text: str) -> Optional[float]:
        """Extract total amount from text."""
        # Patterns for total amount
        amount_patterns = [
            r'totaal[:\s]+[€]?\s*([\d,]+\.?\d*)',
            r'total[:\s]+[€]?\s*([\d,]+\.?\d*)',
            r'te betalen[:\s]+[€]?\s*([\d,]+\.?\d*)',
            r'[€]\s*([\d,]+\.?\d*)',
        ]

        text_lower = text.lower()

        for pattern in amount_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                # Get the last match (usually the total)
                amount_str = matches[-1].replace(',', '.')
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        return None

    @classmethod
    def extract_vat_amounts(cls, text: str) -> Dict[str, float]:
        """Extract VAT amounts from text."""
        vat_amounts = {
            'vat_6': 0.0,
            'vat_9': 0.0,
            'vat_21': 0.0
        }

        # Patterns for VAT amounts
        vat_patterns = [
            (r'btw\s+6%[:\s]+[€]?\s*([\d,]+\.?\d*)', 'vat_6'),
            (r'btw\s+9%[:\s]+[€]?\s*([\d,]+\.?\d*)', 'vat_9'),
            (r'btw\s+21%[:\s]+[€]?\s*([\d,]+\.?\d*)', 'vat_21'),
            (r'vat\s+21%[:\s]+[€]?\s*([\d,]+\.?\d*)', 'vat_21'),
        ]

        text_lower = text.lower()

        for pattern, vat_key in vat_patterns:
            match = re.search(pattern, text_lower)
            if match:
                amount_str = match.group(1).replace(',', '.')
                try:
                    vat_amounts[vat_key] = float(amount_str)
                except ValueError:
                    pass

        return vat_amounts

    @classmethod
    def extract_vendor_name(cls, text: str) -> Optional[str]:
        """Extract vendor name from text."""
        # Usually the vendor name is at the top of the receipt
        lines = text.strip().split('\n')

        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            # Skip empty lines and lines with only numbers
            if line and not line.replace(' ', '').isdigit():
                # Clean up the vendor name
                vendor = re.sub(r'[^\w\s-]', '', line)
                if len(vendor) > 2:  # Minimum length check
                    return vendor.strip()

        return None

    @classmethod
    def extract_invoice_number(cls, text: str) -> Optional[str]:
        """Extract invoice or receipt number from text."""
        # Patterns for invoice numbers
        invoice_patterns = [
            r'bon[:\s]+(\w+)',
            r'factuur[:\s]+(\w+)',
            r'invoice[:\s]+(\w+)',
            r'receipt[:\s]+(\w+)',
            r'nummer[:\s]+(\w+)',
            r'nr[:\s]+(\w+)',
        ]

        text_lower = text.lower()

        for pattern in invoice_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1)

        return None

    @classmethod
    def extract_line_items(cls, text: str) -> List[Dict]:
        """Extract individual line items from receipt."""
        items = []

        # Pattern for line items (simplified)
        item_pattern = r'(.+?)\s+(\d+)[x\*]?\s+[€]?([\d,]+\.?\d*)'

        lines = text.split('\n')

        for line in lines:
            match = re.search(item_pattern, line)
            if match:
                items.append({
                    'description': match.group(1).strip(),
                    'quantity': int(match.group(2)),
                    'price': float(match.group(3).replace(',', '.'))
                })

        return items

    @classmethod
    def calculate_confidence(cls, text: str) -> float:
        """
        Calculate OCR confidence score.

        Args:
            text: OCR extracted text

        Returns:
            Confidence score between 0 and 1
        """
        if not text:
            return 0.0

        # Factors for confidence calculation
        factors = []

        # Check text length
        factors.append(min(len(text) / 500, 1.0))

        # Check for key receipt elements
        key_elements = ['totaal', 'total', 'btw', 'vat', '€', 'datum', 'date']
        text_lower = text.lower()
        element_score = sum(1 for elem in key_elements if elem in text_lower) / len(key_elements)
        factors.append(element_score)

        # Check for numbers (receipts should have numbers)
        numbers = re.findall(r'\d+', text)
        factors.append(min(len(numbers) / 10, 1.0))

        # Calculate average confidence
        confidence = sum(factors) / len(factors)

        return round(confidence, 2)