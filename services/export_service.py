"""Export service for generating reports in various formats."""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
import io
from pathlib import Path

from config import Config
from utils.database_utils_local import get_receipts_for_export
from utils.calculations import calculate_quarterly_vat, calculate_annual_summary

logger = logging.getLogger(__name__)

class ExportService:
    """Service for exporting receipts and reports."""

    @staticmethod
    def export_to_excel(
        receipts: List[Dict],
        include_summary: bool = True,
        include_vat_declaration: bool = False
    ) -> bytes:
        """
        Export receipts to Excel format.

        Args:
            receipts: List of receipt dictionaries
            include_summary: Include summary sheet
            include_vat_declaration: Include VAT declaration sheet

        Returns:
            Excel file as bytes
        """
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book

            # Define formats
            money_format = workbook.add_format({'num_format': '€ #,##0.00'})
            percent_format = workbook.add_format({'num_format': '0%'})
            date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })

            # Main data sheet
            df_receipts = ExportService._prepare_receipts_dataframe(receipts)
            df_receipts.to_excel(writer, sheet_name='Bonnen', index=False)

            worksheet = writer.sheets['Bonnen']

            # Apply formatting to columns
            worksheet.set_column('A:A', 12)  # Nr
            worksheet.set_column('B:B', 12, date_format)  # Datum
            worksheet.set_column('C:C', 25)  # Leverancier
            worksheet.set_column('D:D', 30)  # Categorie
            worksheet.set_column('E:K', 15, money_format)  # Money columns
            worksheet.set_column('L:M', 10, percent_format)  # Percentage columns
            worksheet.set_column('N:P', 15, money_format)  # More money columns
            worksheet.set_column('Q:Q', 40)  # Toelichting

            # Add summary sheet if requested
            if include_summary:
                ExportService._add_summary_sheet(writer, receipts, workbook)

            # Add VAT declaration sheet if requested
            if include_vat_declaration:
                ExportService._add_vat_declaration_sheet(writer, receipts, workbook)

        output.seek(0)
        return output.read()

    @staticmethod
    def export_to_csv(receipts: List[Dict]) -> str:
        """
        Export receipts to CSV format.

        Args:
            receipts: List of receipt dictionaries

        Returns:
            CSV string
        """
        df = ExportService._prepare_receipts_dataframe(receipts)
        return df.to_csv(index=False, sep=';', decimal=',')

    @staticmethod
    def export_to_json(receipts: List[Dict]) -> str:
        """
        Export receipts to JSON format.

        Args:
            receipts: List of receipt dictionaries

        Returns:
            JSON string
        """
        df = ExportService._prepare_receipts_dataframe(receipts)
        return df.to_json(orient='records', date_format='iso', indent=2)

    @staticmethod
    def _prepare_receipts_dataframe(receipts: List[Dict]) -> pd.DataFrame:
        """
        Prepare receipts data for export.

        Args:
            receipts: List of receipt dictionaries

        Returns:
            Formatted DataFrame
        """
        # Create DataFrame with Dutch column names
        export_data = []

        for idx, receipt in enumerate(receipts, 1):
            row = {
                'Nr': idx,
                'Datum': receipt.get('transaction_date'),
                'Winkel/Leverancier': receipt.get('vendor_name'),
                'Categorie kosten': receipt.get('category'),
                'Bedrag excl. BTW': receipt.get('amount_excl_vat', 0),
                'BTW 6%': receipt.get('vat_6', 0),
                'BTW 9%': receipt.get('vat_9', 0),
                'BTW 21%': receipt.get('vat_21', 0),
                'Totaal incl. BTW': receipt.get('total_incl_vat', 0),
                'BTW aftrekbaar %': receipt.get('vat_deductible_percentage', 0) / 100,
                'IB aftrekbaar %': receipt.get('ib_deductible_percentage', 0) / 100,
                'BTW terugvraag': receipt.get('vat_refund', 0),
                'Restant na BTW': receipt.get('total_incl_vat', 0) - receipt.get('vat_refund', 0),
                'Winstaftrek': receipt.get('profit_deduction', 0),
                'Toelichting/motivatie': receipt.get('explanation', '')
            }
            export_data.append(row)

        df = pd.DataFrame(export_data)

        # Convert date column to datetime
        if 'Datum' in df.columns:
            df['Datum'] = pd.to_datetime(df['Datum'])

        return df

    @staticmethod
    def _add_summary_sheet(writer, receipts: List[Dict], workbook):
        """Add summary sheet to Excel export."""

        summary = calculate_annual_summary(receipts)

        # Create summary data
        summary_data = {
            'Omschrijving': [],
            'Waarde': []
        }

        summary_data['Omschrijving'].extend([
            'Totaal aantal bonnen',
            'Totale uitgaven (incl. BTW)',
            'Totaal BTW betaald',
            'Totaal BTW terugvordering',
            'Aftrekbare kosten',
            'Niet-aftrekbare kosten'
        ])

        summary_data['Waarde'].extend([
            summary['receipt_count'],
            summary['total_expenses'],
            summary['total_vat_paid'],
            summary['total_vat_refunded'],
            summary['deductible_expenses'],
            summary['non_deductible_expenses']
        ])

        # Add category breakdown
        summary_data['Omschrijving'].append('')
        summary_data['Waarde'].append('')
        summary_data['Omschrijving'].append('Per Categorie:')
        summary_data['Waarde'].append('')

        for category, data in summary['by_category'].items():
            if data['count'] > 0:
                summary_data['Omschrijving'].append(f"  {category}")
                summary_data['Waarde'].append(data['total'])

        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Samenvatting', index=False)

        # Apply formatting
        worksheet = writer.sheets['Samenvatting']
        money_format = workbook.add_format({'num_format': '€ #,##0.00'})

        worksheet.set_column('A:A', 40)
        worksheet.set_column('B:B', 20, money_format)

    @staticmethod
    def _add_vat_declaration_sheet(writer, receipts: List[Dict], workbook):
        """Add VAT declaration sheet to Excel export."""

        vat_summary = calculate_quarterly_vat(receipts)

        # Create VAT declaration data
        vat_data = {
            'Code': [],
            'Omschrijving': [],
            'Basis': [],
            'BTW': []
        }

        # Add sales data (empty for expenses-only)
        vat_data['Code'].extend(['1a', '1b', '1c', '1d', '1e'])
        vat_data['Omschrijving'].extend([
            'Leveringen/diensten belast met hoog tarief',
            'Leveringen/diensten belast met laag tarief',
            'Leveringen/diensten belast met overige tarieven',
            'Privégebruik',
            'Leveringen/diensten belast met 0%'
        ])
        vat_data['Basis'].extend([0, 0, 0, 0, 0])
        vat_data['BTW'].extend([0, 0, 0, 0, 0])

        # Add separator
        vat_data['Code'].append('')
        vat_data['Omschrijving'].append('Voorbelasting')
        vat_data['Basis'].append('')
        vat_data['BTW'].append('')

        # Add purchase data
        vat_data['Code'].append('5b')
        vat_data['Omschrijving'].append('Voorbelasting')
        vat_data['Basis'].append(vat_summary['total_purchases'])
        vat_data['BTW'].append(vat_summary['deductible_vat'])

        # Add totals
        vat_data['Code'].append('')
        vat_data['Omschrijving'].append('Totalen')
        vat_data['Basis'].append('')
        vat_data['BTW'].append('')

        vat_data['Code'].append('')
        vat_data['Omschrijving'].append('Te betalen/terug te vragen')
        vat_data['Basis'].append('')
        vat_data['BTW'].append(-vat_summary['vat_balance'])

        df_vat = pd.DataFrame(vat_data)
        df_vat.to_excel(writer, sheet_name='BTW Aangifte', index=False)

        # Apply formatting
        worksheet = writer.sheets['BTW Aangifte']
        money_format = workbook.add_format({'num_format': '€ #,##0.00'})

        worksheet.set_column('A:A', 10)
        worksheet.set_column('B:B', 50)
        worksheet.set_column('C:D', 20, money_format)

    @staticmethod
    def generate_quarterly_report(
        user_id: int,
        year: int,
        quarter: int
    ) -> Dict:
        """
        Generate quarterly VAT report.

        Args:
            user_id: User ID
            year: Year
            quarter: Quarter (1-4)

        Returns:
            Report data dictionary
        """
        # Calculate date range
        quarter_dates = {
            1: (f"{year}-01-01", f"{year}-03-31"),
            2: (f"{year}-04-01", f"{year}-06-30"),
            3: (f"{year}-07-01", f"{year}-09-30"),
            4: (f"{year}-10-01", f"{year}-12-31")
        }

        start_date, end_date = quarter_dates[quarter]

        # Get receipts
        receipts = get_receipts_for_export(
            user_id,
            datetime.strptime(start_date, '%Y-%m-%d'),
            datetime.strptime(end_date, '%Y-%m-%d')
        )

        # Calculate VAT summary
        vat_summary = calculate_quarterly_vat(receipts)

        return {
            'period': f"Q{quarter} {year}",
            'start_date': start_date,
            'end_date': end_date,
            'receipt_count': len(receipts),
            'vat_summary': vat_summary,
            'receipts': receipts
        }

    @staticmethod
    def generate_annual_report(user_id: int, year: int) -> Dict:
        """
        Generate annual report for income tax.

        Args:
            user_id: User ID
            year: Year

        Returns:
            Report data dictionary
        """
        # Get receipts for the year
        receipts = get_receipts_for_export(
            user_id,
            datetime(year, 1, 1),
            datetime(year, 12, 31)
        )

        # Calculate annual summary
        annual_summary = calculate_annual_summary(receipts)

        return {
            'year': year,
            'receipt_count': len(receipts),
            'summary': annual_summary,
            'receipts': receipts
        }