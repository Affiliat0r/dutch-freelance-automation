"""Receipt processing pipeline orchestrating OCR and LLM services."""

import logging
from typing import Dict, Optional, List, Tuple
from pathlib import Path
from datetime import datetime

from services.ocr_service import OCRService
from services.llm_service import LLMService
from utils.calculations import calculate_tax_deductions
from utils.database_utils import (
    save_extracted_data,
    update_receipt_status,
    log_audit_event
)

logger = logging.getLogger(__name__)

class ReceiptProcessor:
    """Main processing pipeline for receipts."""

    def __init__(self):
        """Initialize the processor."""
        self.ocr_service = OCRService()
        self.llm_service = LLMService()

    def process_receipt(
        self,
        receipt_id: int,
        file_path: str,
        user_id: int = None
    ) -> Dict:
        """
        Process a single receipt through the complete pipeline.

        Args:
            receipt_id: Database receipt ID
            file_path: Path to receipt file
            user_id: User ID for audit

        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'receipt_id': receipt_id,
            'error': None,
            'data': {}
        }

        try:
            # Step 1: Update status to processing
            update_receipt_status(receipt_id, 'processing')

            # Step 2: OCR extraction
            logger.info(f"Starting OCR for receipt {receipt_id}")
            ocr_result = self.ocr_service.process_receipt(file_path)

            if not ocr_result['success']:
                raise Exception(f"OCR failed: {ocr_result.get('error')}")

            # Step 3: LLM processing for data extraction
            logger.info(f"Starting LLM processing for receipt {receipt_id}")
            llm_result = self.llm_service.process_receipt_text(
                ocr_result['raw_text'],
                file_path
            )

            if not llm_result['success']:
                # Fall back to structured OCR data
                extracted_data = ocr_result['structured_data']
            else:
                extracted_data = llm_result['data']

            # Step 4: Categorization
            category = self.llm_service.categorize_expense(extracted_data)
            extracted_data['category'] = category

            # Step 5: Tax calculations
            tax_calcs = self.llm_service.calculate_tax_deductions(extracted_data)
            extracted_data.update(tax_calcs)

            # Step 6: Prepare data for database
            db_data = self._prepare_database_data(extracted_data, ocr_result)

            # Step 7: Save to database
            save_success = save_extracted_data(receipt_id, db_data)

            if not save_success:
                raise Exception("Failed to save extracted data to database")

            # Step 8: Update status to completed
            update_receipt_status(receipt_id, 'completed')

            # Step 9: Log audit event
            if user_id:
                log_audit_event(
                    user_id=user_id,
                    action='process',
                    entity_type='receipt',
                    entity_id=receipt_id,
                    new_values={'status': 'completed', 'category': category}
                )

            result['success'] = True
            result['data'] = extracted_data

            logger.info(f"Successfully processed receipt {receipt_id}")

        except Exception as e:
            logger.error(f"Error processing receipt {receipt_id}: {e}")
            result['error'] = str(e)

            # Update status to failed
            update_receipt_status(receipt_id, 'failed', str(e))

            if user_id:
                log_audit_event(
                    user_id=user_id,
                    action='process_failed',
                    entity_type='receipt',
                    entity_id=receipt_id,
                    new_values={'error': str(e)}
                )

        return result

    def _prepare_database_data(self, extracted_data: Dict, ocr_result: Dict) -> Dict:
        """
        Prepare extracted data for database storage.

        Args:
            extracted_data: Data from LLM/OCR extraction
            ocr_result: OCR service result

        Returns:
            Dictionary formatted for database
        """
        # Parse date
        transaction_date = None
        if extracted_data.get('date'):
            try:
                from dateutil import parser
                transaction_date = parser.parse(extracted_data['date'])
            except:
                transaction_date = datetime.now()

        # Get VAT breakdown
        vat_breakdown = extracted_data.get('vat_breakdown', {})

        # Calculate totals
        total_vat = sum(float(v) for v in vat_breakdown.values())
        amount_excl_vat = extracted_data.get('subtotal', 0) or extracted_data.get('total_amount', 0) - total_vat

        db_data = {
            'transaction_date': transaction_date,
            'vendor_name': extracted_data.get('vendor_name'),
            'vendor_address': extracted_data.get('vendor_address'),
            'invoice_number': extracted_data.get('invoice_number'),
            'detected_language': extracted_data.get('detected_language', ocr_result.get('language')),
            'expense_category': extracted_data.get('category'),
            'amount_excl_vat': amount_excl_vat,
            'vat_6_amount': vat_breakdown.get('6', 0),
            'vat_9_amount': vat_breakdown.get('9', 0),
            'vat_21_amount': vat_breakdown.get('21', 0),
            'total_incl_vat': extracted_data.get('total_amount', 0),
            'vat_deductible_percentage': extracted_data.get('vat_deductible_percentage'),
            'ib_deductible_percentage': extracted_data.get('ib_deductible_percentage'),
            'vat_refund_amount': extracted_data.get('vat_deductible_amount'),
            'remainder_after_vat': extracted_data.get('remainder_after_vat'),
            'profit_deduction': extracted_data.get('profit_deduction'),
            'explanation': extracted_data.get('notes'),
            'items_json': extracted_data.get('items', []),
            'raw_ocr_text': ocr_result.get('raw_text'),
            'confidence_score': extracted_data.get('confidence', ocr_result.get('confidence')),
            'extraction_version': '1.0',
            'manual_review_required': extracted_data.get('confidence', 1) < 0.7
        }

        return db_data

    def batch_process_receipts(
        self,
        receipt_files: List[Dict],
        user_id: int = None,
        callback=None
    ) -> Dict:
        """
        Process multiple receipts in batch.

        Args:
            receipt_files: List of dictionaries with receipt_id and file_path
            user_id: User ID for audit
            callback: Optional callback function for progress updates

        Returns:
            Dictionary with batch processing results
        """
        results = {
            'total': len(receipt_files),
            'successful': 0,
            'failed': 0,
            'results': []
        }

        for idx, receipt_file in enumerate(receipt_files):
            # Update progress if callback provided
            if callback:
                callback(idx + 1, len(receipt_files), f"Processing {receipt_file.get('filename', 'receipt')}")

            # Process receipt
            result = self.process_receipt(
                receipt_file['receipt_id'],
                receipt_file['file_path'],
                user_id
            )

            results['results'].append(result)

            if result['success']:
                results['successful'] += 1
            else:
                results['failed'] += 1

        logger.info(f"Batch processing completed: {results['successful']} successful, {results['failed']} failed")

        return results

    def reprocess_failed_receipts(self, user_id: int = None) -> Dict:
        """
        Reprocess all failed receipts.

        Args:
            user_id: User ID for audit

        Returns:
            Dictionary with reprocessing results
        """
        from utils.database_utils import search_receipts

        # Get all failed receipts
        failed_receipts = search_receipts(
            user_id=user_id,
            status='failed'
        )

        if not failed_receipts:
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'message': 'No failed receipts to reprocess'
            }

        # Prepare for batch processing
        receipt_files = [
            {
                'receipt_id': r['id'],
                'file_path': r.get('file_path'),
                'filename': r.get('filename')
            }
            for r in failed_receipts
        ]

        # Process batch
        results = self.batch_process_receipts(receipt_files, user_id)

        return results

    def validate_extraction(self, extracted_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate extracted data for completeness and accuracy.

        Args:
            extracted_data: Extracted data dictionary

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check required fields
        required_fields = ['vendor_name', 'total_amount', 'date']
        for field in required_fields:
            if not extracted_data.get(field):
                issues.append(f"Missing required field: {field}")

        # Validate amounts
        if extracted_data.get('total_amount'):
            try:
                amount = float(extracted_data['total_amount'])
                if amount <= 0:
                    issues.append("Total amount must be positive")
                if amount > 100000:
                    issues.append("Total amount seems unusually high")
            except:
                issues.append("Invalid total amount format")

        # Validate VAT breakdown
        vat_breakdown = extracted_data.get('vat_breakdown', {})
        total_vat = sum(float(v) for v in vat_breakdown.values())

        if total_vat > 0:
            amount_excl = extracted_data.get('total_amount', 0) - total_vat
            if amount_excl < 0:
                issues.append("VAT amount exceeds total amount")

        # Validate date
        if extracted_data.get('date'):
            try:
                from dateutil import parser
                date = parser.parse(extracted_data['date'])
                if date > datetime.now():
                    issues.append("Transaction date is in the future")
            except:
                issues.append("Invalid date format")

        # Check confidence
        confidence = extracted_data.get('confidence', 0)
        if confidence < 0.5:
            issues.append(f"Low confidence score: {confidence:.2f}")

        is_valid = len(issues) == 0

        return is_valid, issues