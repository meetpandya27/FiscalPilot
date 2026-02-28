"""
AI Chat Interface — conversational finance assistant (like "Ask Digits").

Provides a natural language interface for querying financial data,
asking questions about expenses, trends, and getting AI-powered insights.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fiscalpilot.models.financial import Transaction

logger = logging.getLogger("fiscalpilot.analyzers.chat")


class QueryType(str, Enum):
    """Types of queries the chat can handle."""
    
    SPENDING_SUMMARY = "spending_summary"
    VENDOR_LOOKUP = "vendor_lookup"
    CATEGORY_BREAKDOWN = "category_breakdown"
    TREND_ANALYSIS = "trend_analysis"
    ANOMALY_INQUIRY = "anomaly_inquiry"
    BUDGET_STATUS = "budget_status"
    COMPARISON = "comparison"
    FORECAST = "forecast"
    GENERAL = "general"


@dataclass
class ChatContext:
    """Context for a chat session."""
    
    user_id: str | None = None
    company_id: str | None = None
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    current_date_range: tuple[date | None, date | None] = (None, None)
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Response from the chat assistant."""
    
    answer: str
    query_type: QueryType
    data: dict[str, Any] = field(default_factory=dict)
    visualizations: list[dict[str, Any]] = field(default_factory=list)
    follow_up_suggestions: list[str] = field(default_factory=list)
    confidence: float = 1.0


class FinancialChatAssistant:
    """
    Conversational AI assistant for financial queries.
    
    Inspired by Digits' "Ask Digits" feature — allows users to ask natural
    language questions about their finances and get instant answers.
    
    Example queries:
    - "How much did I spend on marketing last month?"
    - "What's my largest expense category?"
    - "Show me unusual transactions this week"
    - "Compare my food costs to last quarter"
    - "Which vendors am I spending the most with?"
    """
    
    # Query patterns for classification
    SPENDING_PATTERNS = ["spend", "spent", "cost", "paid", "expense", "how much"]
    VENDOR_PATTERNS = ["vendor", "supplier", "merchant", "company", "paid to", "who"]
    CATEGORY_PATTERNS = ["category", "breakdown", "by type", "categorize"]
    TREND_PATTERNS = ["trend", "over time", "compare", "vs", "versus", "growth", "change"]
    ANOMALY_PATTERNS = ["unusual", "anomaly", "weird", "suspicious", "outlier", "flag"]
    BUDGET_PATTERNS = ["budget", "limit", "allowance", "target", "goal"]
    
    def __init__(self, transactions: list[Transaction] | None = None):
        """Initialize the chat assistant with transaction data."""
        self.transactions = transactions or []
        self.context = ChatContext()
        
    def query(self, question: str, context: ChatContext | None = None) -> ChatResponse:
        """
        Process a natural language question about finances.
        
        Args:
            question: Natural language question from the user.
            context: Optional conversation context for follow-ups.
            
        Returns:
            ChatResponse with answer, data, and follow-up suggestions.
        """
        if context:
            self.context = context
            
        # Add to conversation history
        self.context.conversation_history.append({"role": "user", "content": question})
        
        # Classify the query type
        query_type = self._classify_query(question.lower())
        
        # Route to appropriate handler
        handlers = {
            QueryType.SPENDING_SUMMARY: self._handle_spending_query,
            QueryType.VENDOR_LOOKUP: self._handle_vendor_query,
            QueryType.CATEGORY_BREAKDOWN: self._handle_category_query,
            QueryType.TREND_ANALYSIS: self._handle_trend_query,
            QueryType.ANOMALY_INQUIRY: self._handle_anomaly_query,
            QueryType.BUDGET_STATUS: self._handle_budget_query,
            QueryType.COMPARISON: self._handle_comparison_query,
            QueryType.FORECAST: self._handle_forecast_query,
            QueryType.GENERAL: self._handle_general_query,
        }
        
        handler = handlers.get(query_type, self._handle_general_query)
        response = handler(question)
        
        # Add response to history
        self.context.conversation_history.append({"role": "assistant", "content": response.answer})
        
        return response
    
    def _classify_query(self, question: str) -> QueryType:
        """Classify the type of query based on keywords."""
        if any(p in question for p in self.ANOMALY_PATTERNS):
            return QueryType.ANOMALY_INQUIRY
        if any(p in question for p in self.BUDGET_PATTERNS):
            return QueryType.BUDGET_STATUS
        if any(p in question for p in self.TREND_PATTERNS):
            return QueryType.TREND_ANALYSIS
        if any(p in question for p in self.VENDOR_PATTERNS):
            return QueryType.VENDOR_LOOKUP
        if any(p in question for p in self.CATEGORY_PATTERNS):
            return QueryType.CATEGORY_BREAKDOWN
        if any(p in question for p in self.SPENDING_PATTERNS):
            return QueryType.SPENDING_SUMMARY
        return QueryType.GENERAL
    
    def _handle_spending_query(self, question: str) -> ChatResponse:
        """Handle questions about spending amounts."""
        if not self.transactions:
            return ChatResponse(
                answer="I don't have any transaction data loaded. Please upload your transactions first.",
                query_type=QueryType.SPENDING_SUMMARY,
                follow_up_suggestions=["How do I upload transactions?", "What file formats do you support?"]
            )
        
        # Calculate total spending
        expenses = [t for t in self.transactions if t.is_expense]
        total = sum(t.amount for t in expenses)
        count = len(expenses)
        
        # Group by category
        by_category: dict[str, float] = {}
        for t in expenses:
            cat = t.category.value if t.category else "uncategorized"
            by_category[cat] = by_category.get(cat, 0) + t.amount
        
        top_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]
        
        answer = f"You've spent **${total:,.2f}** across {count} transactions.\n\n"
        answer += "**Top spending categories:**\n"
        for cat, amt in top_categories:
            pct = (amt / total * 100) if total > 0 else 0
            answer += f"- {cat.replace('_', ' ').title()}: ${amt:,.2f} ({pct:.1f}%)\n"
        
        return ChatResponse(
            answer=answer,
            query_type=QueryType.SPENDING_SUMMARY,
            data={"total": total, "by_category": by_category, "transaction_count": count},
            follow_up_suggestions=[
                "Show me spending by vendor",
                "What are my unusual expenses?",
                "Compare this to last month"
            ]
        )
    
    def _handle_vendor_query(self, question: str) -> ChatResponse:
        """Handle questions about vendor spending."""
        if not self.transactions:
            return ChatResponse(
                answer="No transaction data available.",
                query_type=QueryType.VENDOR_LOOKUP
            )
        
        # Group by vendor
        by_vendor: dict[str, dict] = {}
        for t in self.transactions:
            vendor = t.vendor or "Unknown"
            if vendor not in by_vendor:
                by_vendor[vendor] = {"total": 0, "count": 0, "transactions": []}
            by_vendor[vendor]["total"] += t.amount
            by_vendor[vendor]["count"] += 1
        
        top_vendors = sorted(by_vendor.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
        
        answer = "**Top vendors by spend:**\n\n"
        for i, (vendor, data) in enumerate(top_vendors, 1):
            answer += f"{i}. **{vendor}**: ${data['total']:,.2f} ({data['count']} transactions)\n"
        
        return ChatResponse(
            answer=answer,
            query_type=QueryType.VENDOR_LOOKUP,
            data={"by_vendor": by_vendor},
            follow_up_suggestions=[
                f"Show me all transactions from {top_vendors[0][0] if top_vendors else 'a vendor'}",
                "Are there any duplicate payments?",
                "Which vendors have price increases?"
            ]
        )
    
    def _handle_category_query(self, question: str) -> ChatResponse:
        """Handle questions about category breakdowns."""
        if not self.transactions:
            return ChatResponse(
                answer="No transaction data available.",
                query_type=QueryType.CATEGORY_BREAKDOWN
            )
        
        # Group by category
        by_category: dict[str, dict] = {}
        for t in self.transactions:
            cat = t.category.value if t.category else "uncategorized"
            if cat not in by_category:
                by_category[cat] = {"total": 0, "count": 0}
            by_category[cat]["total"] += abs(t.amount)
            by_category[cat]["count"] += 1
        
        total = sum(d["total"] for d in by_category.values())
        sorted_cats = sorted(by_category.items(), key=lambda x: x[1]["total"], reverse=True)
        
        answer = "**Expense breakdown by category:**\n\n"
        for cat, data in sorted_cats:
            pct = (data["total"] / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            answer += f"**{cat.replace('_', ' ').title()}**\n"
            answer += f"  ${data['total']:,.2f} ({pct:.1f}%) {bar}\n\n"
        
        return ChatResponse(
            answer=answer,
            query_type=QueryType.CATEGORY_BREAKDOWN,
            data={"by_category": by_category, "total": total},
            visualizations=[{"type": "pie_chart", "data": by_category}],
            follow_up_suggestions=[
                "Which category grew the most?",
                "Show me uncategorized transactions",
                "What's typically categorized wrong?"
            ]
        )
    
    def _handle_trend_query(self, question: str) -> ChatResponse:
        """Handle questions about trends and comparisons."""
        return ChatResponse(
            answer="Trend analysis shows your spending patterns over time. This feature requires historical data spanning multiple periods.",
            query_type=QueryType.TREND_ANALYSIS,
            follow_up_suggestions=[
                "Show me monthly spending",
                "What's my burn rate?",
                "Forecast next month's expenses"
            ]
        )
    
    def _handle_anomaly_query(self, question: str) -> ChatResponse:
        """Handle questions about unusual transactions."""
        return ChatResponse(
            answer="I can detect unusual transactions using statistical analysis. Run an anomaly scan on your data to see flagged items.",
            query_type=QueryType.ANOMALY_INQUIRY,
            follow_up_suggestions=[
                "Run anomaly detection",
                "Show me Benford's Law analysis",
                "What transactions are flagged?"
            ]
        )
    
    def _handle_budget_query(self, question: str) -> ChatResponse:
        """Handle questions about budgets."""
        return ChatResponse(
            answer="Budget tracking helps you monitor spending against targets. Set up budgets by category to get alerts when you're over.",
            query_type=QueryType.BUDGET_STATUS,
            follow_up_suggestions=[
                "Create a new budget",
                "Show budget vs actual",
                "What categories are over budget?"
            ]
        )
    
    def _handle_comparison_query(self, question: str) -> ChatResponse:
        """Handle comparison queries."""
        return ChatResponse(
            answer="I can compare your spending across different time periods or against industry benchmarks.",
            query_type=QueryType.COMPARISON,
            follow_up_suggestions=[
                "Compare to last quarter",
                "How do I compare to industry?",
                "Show year-over-year change"
            ]
        )
    
    def _handle_forecast_query(self, question: str) -> ChatResponse:
        """Handle forecast queries."""
        return ChatResponse(
            answer="Cash flow forecasting predicts your future financial position based on historical patterns and known upcoming payments.",
            query_type=QueryType.FORECAST,
            follow_up_suggestions=[
                "Forecast next 3 months",
                "When will I run out of cash?",
                "What's my projected runway?"
            ]
        )
    
    def _handle_general_query(self, question: str) -> ChatResponse:
        """Handle general queries."""
        return ChatResponse(
            answer="I'm your AI financial assistant. I can help you understand your spending, find anomalies, track budgets, and more.\n\n**Try asking:**\n- How much did I spend last month?\n- What are my top vendors?\n- Show me unusual transactions\n- What's my category breakdown?",
            query_type=QueryType.GENERAL,
            follow_up_suggestions=[
                "Show me my spending summary",
                "What can you help me with?",
                "How do I get started?"
            ]
        )


# Convenience function
def ask(question: str, transactions: list[Transaction] | None = None) -> ChatResponse:
    """Quick way to ask a question about finances."""
    assistant = FinancialChatAssistant(transactions)
    return assistant.query(question)
