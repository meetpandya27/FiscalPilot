"""Tests for the Invoice Processor (OCR) module."""

import pytest
from datetime import date
from fiscalpilot.analyzers.invoice_processor import (
    InvoiceProcessor,
    ExtractedInvoice,
    ExtractedLineItem,
    OCRBackend,
    InvoiceStatus,
    process_invoice,
)


class TestExtractedLineItem:
    """Test ExtractedLineItem dataclass."""
    
    def test_line_item_creation(self):
        """Test basic line item creation."""
        item = ExtractedLineItem(
            description="Widget A",
            quantity=10,
            unit_price=25.0,
            amount=250.0,
        )
        
        assert item.description == "Widget A"
        assert item.quantity == 10
        assert item.amount == 250.0


class TestExtractedInvoice:
    """Test ExtractedInvoice dataclass."""
    
    def test_invoice_creation(self):
        """Test basic invoice creation."""
        invoice = ExtractedInvoice(
            invoice_number="INV-001",
            vendor_name="Acme Corp",
            invoice_date=date(2025, 1, 15),
            total_amount=1000.0,
        )
        
        assert invoice.invoice_number == "INV-001"
        assert invoice.vendor_name == "Acme Corp"
        assert invoice.total_amount == 1000.0
    
    def test_invoice_with_line_items(self):
        """Test invoice with line items."""
        items = [
            ExtractedLineItem("Item 1", 2, 50.0, 100.0),
            ExtractedLineItem("Item 2", 3, 100.0, 300.0),
        ]
        
        invoice = ExtractedInvoice(
            invoice_number="INV-002",
            vendor_name="Supplier Inc",
            invoice_date=date(2025, 1, 20),
            total_amount=400.0,
            line_items=items,
        )
        
        assert len(invoice.line_items) == 2
    
    def test_invoice_with_tax(self):
        """Test invoice with tax and totals."""
        invoice = ExtractedInvoice(
            invoice_number="INV-003",
            vendor_name="Vendor",
            invoice_date=date(2025, 1, 25),
            subtotal=100.0,
            tax_amount=8.0,
            total_amount=108.0,
        )
        
        assert invoice.tax_amount == 8.0
        assert invoice.total_amount == 108.0
    
    def test_invoice_status(self):
        """Test invoice status."""
        invoice = ExtractedInvoice(
            invoice_number="INV-004",
            vendor_name="Test Vendor",
            invoice_date=date(2025, 2, 1),
            total_amount=500.0,
            status=InvoiceStatus.EXTRACTED,
        )
        
        assert invoice.status == InvoiceStatus.EXTRACTED
    
    def test_invoice_overall_confidence(self):
        """Test overall confidence calculation."""
        invoice = ExtractedInvoice(
            invoice_number="INV-005",
            vendor_name="Vendor",
            total_amount=100.0,
            confidence_scores={"invoice_number": 0.9, "vendor": 0.8, "total": 0.95},
        )
        
        assert 0.8 < invoice.overall_confidence < 0.95
    
    def test_invoice_needs_review(self):
        """Test needs_review property."""
        # Low confidence => needs review
        low_conf = ExtractedInvoice(
            invoice_number="INV-006",
            vendor_name="Vendor",
            total_amount=100.0,
            confidence_scores={"invoice_number": 0.5, "vendor": 0.5},
        )
        
        assert low_conf.needs_review is True
        
        # High confidence with total => doesn't need review
        high_conf = ExtractedInvoice(
            invoice_number="INV-007",
            vendor_name="Vendor",
            total_amount=100.0,
            confidence_scores={
                "invoice_number": 0.95,
                "vendor": 0.95,
                "total": 0.95,
            },
        )
        
        assert high_conf.needs_review is False


class TestInvoiceProcessor:
    """Test InvoiceProcessor class."""
    
    def test_init_default(self):
        """Test default initialization."""
        processor = InvoiceProcessor()
        assert processor.backend == OCRBackend.TESSERACT
    
    def test_init_with_mock_backend(self):
        """Test initialization with mock backend."""
        processor = InvoiceProcessor(backend=OCRBackend.MOCK)
        assert processor.backend == OCRBackend.MOCK


class TestOCRBackend:
    """Test OCR backend enum."""
    
    def test_backend_values(self):
        """Test backend enum values."""
        assert OCRBackend.TESSERACT.value == "tesseract"
        assert OCRBackend.AZURE_FORM_RECOGNIZER.value == "azure"
        assert OCRBackend.GOOGLE_VISION.value == "google"
        assert OCRBackend.AWS_TEXTRACT.value == "aws"
        assert OCRBackend.MOCK.value == "mock"


class TestInvoiceStatus:
    """Test InvoiceStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert InvoiceStatus.PENDING.value == "pending"
        assert InvoiceStatus.PROCESSING.value == "processing"
        assert InvoiceStatus.EXTRACTED.value == "extracted"
        assert InvoiceStatus.VERIFIED.value == "verified"
        assert InvoiceStatus.FAILED.value == "failed"
