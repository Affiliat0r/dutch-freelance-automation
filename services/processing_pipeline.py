"""Simplified receipt processing pipeline - ONLY uses Gemini Vision."""

import logging
from typing import Dict
from pathlib import Path
from datetime import datetime

from services.llm_service import LLMService
from utils.database_utils import (
    save_extracted_data,
    update_receipt_status,
    log_audit_event
)

logger = logging.getLogger(__name__)

class ReceiptProcessor:
    """Simplified processor - uses ONLY Gemini Vision."""

    def __init__(self):
        """Initialize the processor."""
        self.llm_service = LLMService()

    def process_receipt(
        self,
        receipt_id: int,
        file_path: str,
        user_id: int = None
    ) -> Dict:
        """
        Process a receipt using ONLY Gemini Vision.

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

            # Step 2: Process with Gemini Vision ONLY
            logger.info(f"Processing receipt {receipt_id} with Gemini Vision")
            llm_result = self.llm_service.process_receipt_file(file_path)

            if not llm_result['success']:
                raise Exception(f"Gemini processing failed: {llm_result.get('error')}")

            extracted_data = llm_result['data']

            # Step 3: Prepare data for database
            db_data = self._prepare_database_data(extracted_data, file_path)

            # Step 4: Save to database
            save_success = save_extracted_data(receipt_id, db_data)

            if not save_success:
                raise Exception("Failed to save extracted data to database")

            # Step 5: Update status to completed
            update_receipt_status(receipt_id, 'completed')

            # Step 6: Log audit event
            if user_id:
                log_audit_event(
                    user_id=user_id,
                    action='process',
                    entity_type='receipt',
                    entity_id=receipt_id,
                    new_values={'status': 'completed', 'category': extracted_data.get('category')}
                )

            result['success'] = True
            result['data'] = extracted_data
            result['raw_text'] = llm_result.get('raw_text', '')  # Step 1
            result['structured_data_json'] = llm_result.get('structured_data_json', '')  # Step 2
            result['extracted_category'] = llm_result.get('extracted_category', '')  # Step 3

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

    def _prepare_database_data(self, extracted_data: Dict, file_path: str) -> Dict:
        """
        Prepare extracted data for database storage.

        Args:
            extracted_data: Data from Gemini Vision
            file_path: Path to receipt file

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

        db_data = {
            'transaction_date': transaction_date,
            'vendor_name': extracted_data.get('vendor_name'),
            'vendor_address': extracted_data.get('vendor_address'),
            'invoice_number': extracted_data.get('invoice_number'),
            'detected_language': extracted_data.get('detected_language', 'nl'),
            'expense_category': extracted_data.get('category'),
            'amount_excl_vat': extracted_data.get('amount_excl_vat', 0),
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
            'raw_ocr_text': '',  # Not used anymore
            'confidence_score': extracted_data.get('confidence', 0.8),
            'extraction_version': '2.0-gemini-only',
            'manual_review_required': extracted_data.get('confidence', 1) < 0.7
        }

        return db_data
