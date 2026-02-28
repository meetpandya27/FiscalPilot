"""Tests for the AI Chat Interface module."""

import pytest
from datetime import date
from fiscalpilot.analyzers.chat import (
    FinancialChatAssistant,
    ChatContext,
    ChatResponse,
    QueryType,
    ask,
)
from fiscalpilot.models.financial import Transaction, TransactionType, ExpenseCategory


class TestFinancialChatAssistant:
    """Test the FinancialChatAssistant class."""
    
    def test_init_empty(self):
        """Test initialization without transactions."""
        assistant = FinancialChatAssistant()
        assert assistant.transactions == []
        assert isinstance(assistant.context, ChatContext)
    
    def test_init_with_transactions(self):
        """Test initialization with transactions."""
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=100.0,
                description="Test transaction",
                type=TransactionType.EXPENSE,
            )
        ]
        assistant = FinancialChatAssistant(transactions)
        assert len(assistant.transactions) == 1
    
    def test_query_classification_spending(self):
        """Test query classification for spending questions."""
        assistant = FinancialChatAssistant()
        
        questions = [
            "How much did I spend?",
            "What was spent on marketing?",
            "Show me expenses",
        ]
        
        for q in questions:
            query_type = assistant._classify_query(q.lower())
            assert query_type == QueryType.SPENDING_SUMMARY
    
    def test_query_classification_vendor(self):
        """Test query classification for vendor questions."""
        assistant = FinancialChatAssistant()
        
        questions = [
            "Who are my top vendors?",
            "Show me supplier spending",
            "Which merchant did I pay most?",
        ]
        
        for q in questions:
            query_type = assistant._classify_query(q.lower())
            assert query_type == QueryType.VENDOR_LOOKUP
    
    def test_query_classification_anomaly(self):
        """Test query classification for anomaly questions."""
        assistant = FinancialChatAssistant()
        
        questions = [
            "Show me unusual transactions",
            "Any suspicious activity?",
            "Find outliers",
        ]
        
        for q in questions:
            query_type = assistant._classify_query(q.lower())
            assert query_type == QueryType.ANOMALY_INQUIRY
    
    def test_spending_query_no_data(self):
        """Test spending query with no transaction data."""
        assistant = FinancialChatAssistant()
        response = assistant.query("How much did I spend?")
        
        assert isinstance(response, ChatResponse)
        assert response.query_type == QueryType.SPENDING_SUMMARY
        assert "don't have any transaction data" in response.answer
    
    def test_spending_query_with_data(self):
        """Test spending query with transaction data."""
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Office supplies",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.SUPPLIES,
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=-250.0,
                description="Marketing campaign",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.MARKETING,
            ),
        ]
        assistant = FinancialChatAssistant(transactions)
        response = assistant.query("How much did I spend?")
        
        assert isinstance(response, ChatResponse)
        assert "350" in response.answer  # $350 total (shown as negative for expenses)
        assert abs(response.data.get("total")) == 350.0
    
    def test_vendor_query_with_data(self):
        """Test vendor query with transaction data."""
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Office supplies",
                type=TransactionType.EXPENSE,
                vendor="Staples",
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=-250.0,
                description="More supplies",
                type=TransactionType.EXPENSE,
                vendor="Staples",
            ),
            Transaction(
                date=date(2025, 1, 17),
                amount=-50.0,
                description="Coffee",
                type=TransactionType.EXPENSE,
                vendor="Starbucks",
            ),
        ]
        assistant = FinancialChatAssistant(transactions)
        response = assistant.query("Who are my top vendors?")
        
        assert "Staples" in response.answer
        assert response.data.get("by_vendor") is not None
    
    def test_conversation_history(self):
        """Test that conversation history is tracked."""
        assistant = FinancialChatAssistant()
        
        assistant.query("Hello")
        assistant.query("How much did I spend?")
        
        assert len(assistant.context.conversation_history) == 4  # 2 user + 2 assistant
    
    def test_follow_up_suggestions(self):
        """Test that follow-up suggestions are provided."""
        assistant = FinancialChatAssistant()
        response = assistant.query("What can you help me with?")
        
        assert len(response.follow_up_suggestions) > 0
    
    def test_ask_convenience_function(self):
        """Test the ask() convenience function."""
        response = ask("How much did I spend?")
        assert isinstance(response, ChatResponse)


class TestChatContext:
    """Test the ChatContext class."""
    
    def test_default_values(self):
        """Test default context values."""
        context = ChatContext()
        assert context.user_id is None
        assert context.company_id is None
        assert context.conversation_history == []
        assert context.current_date_range == (None, None)
        assert context.filters == {}
    
    def test_with_values(self):
        """Test context with custom values."""
        context = ChatContext(
            user_id="user123",
            company_id="company456",
        )
        assert context.user_id == "user123"
        assert context.company_id == "company456"
