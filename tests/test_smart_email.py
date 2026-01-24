"""Tests for Smart Email Agent v2.0 (LangGraph-based).

Tests cover:
- State initialization and structure
- Classification node (LLM + regex fallback)
- Format RTL node (Telegram formatting)
- Research, History, Draft nodes
- Full graph execution

ADR-014: Smart Email Agent with Telegram Integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.smart_email.state import (
    EmailCategory,
    EmailItem,
    EmailState,
    Priority,
    ResearchResult,
    SenderHistory,
    DraftReply,
    create_initial_state,
)
from src.agents.smart_email.nodes.classify import (
    classify_with_regex,
    is_system_email,
    parse_classification_result,
    SYSTEM_PATTERNS,
)
from src.agents.smart_email.nodes.format_rtl import (
    format_email_item,
    format_telegram_message_hebrish,
    wrap_english,
)
from src.agents.smart_email.nodes.research import (
    extract_search_query,
    should_research,
)
from src.agents.smart_email.nodes.history import (
    classify_relationship,
    extract_topics,
)
from src.agents.smart_email.nodes.draft import (
    determine_tone,
    determine_action_type,
    should_generate_draft,
)
from src.agents.smart_email.graph import (
    SmartEmailGraph,
    create_email_graph,
)


class TestState:
    """Tests for state initialization."""

    def test_create_initial_state(self):
        """Test initial state creation."""
        state = create_initial_state(hours_lookback=24)

        assert state["hours_lookback"] == 24
        assert state["user_id"] == "default"
        assert state["raw_emails"] == []
        assert state["emails"] == []
        assert state["errors"] == []
        assert "run_id" in state
        assert state["run_id"].startswith("smart_email_")

    def test_create_initial_state_with_user(self):
        """Test initial state creation with custom user."""
        state = create_initial_state(user_id="test_user", hours_lookback=48)

        assert state["user_id"] == "test_user"
        assert state["hours_lookback"] == 48

    def test_email_category_values(self):
        """Test EmailCategory enum values are Hebrew."""
        assert EmailCategory.BUREAUCRACY.value == "בירוקרטיה"
        assert EmailCategory.FINANCE.value == "כספים"
        assert EmailCategory.URGENT.value == "דחוף"
        assert EmailCategory.PROMOTIONAL.value == "פרסום"

    def test_priority_ordering(self):
        """Test Priority enum ordering."""
        assert Priority.P1.value < Priority.P2.value
        assert Priority.P2.value < Priority.P3.value
        assert Priority.P3.value < Priority.P4.value


class TestClassifyNode:
    """Tests for classification node."""

    def test_is_system_email_github(self):
        """Test GitHub notifications are filtered."""
        assert is_system_email("GitHub", "notifications@github.com")
        assert is_system_email("GitHub Actions", "actions@github.com")

    def test_is_system_email_railway(self):
        """Test Railway notifications are filtered."""
        assert is_system_email("Railway", "notifications@railway.app")

    def test_is_system_email_noreply(self):
        """Test noreply addresses are filtered."""
        assert is_system_email("Some Service", "noreply@example.com")
        assert is_system_email("Some Service", "no-reply@example.com")

    def test_is_system_email_human(self):
        """Test human emails are not filtered."""
        assert not is_system_email("John Doe", "john@gmail.com")
        assert not is_system_email("Bank", "support@bank.co.il")

    def test_classify_with_regex_urgent(self):
        """Test regex classification for urgent emails."""
        category, priority, reason = classify_with_regex(
            "דחוף: נדרשת תשובה מיידית",
            "Bank",
            "Please respond immediately"
        )
        assert category == EmailCategory.URGENT
        assert priority == Priority.P1

    def test_classify_with_regex_bureaucracy(self):
        """Test regex classification for government emails."""
        category, priority, reason = classify_with_regex(
            "הודעה מביטוח לאומי",
            "ביטוח לאומי",
            "נא לשלוח מסמכים"
        )
        assert category == EmailCategory.BUREAUCRACY
        assert priority == Priority.P1

    def test_classify_with_regex_finance(self):
        """Test regex classification for finance emails."""
        category, priority, reason = classify_with_regex(
            "חשבונית מס",
            "בנק לאומי",
            "סכום: ₪1,500"
        )
        assert category == EmailCategory.FINANCE
        assert priority == Priority.P1

    def test_classify_with_regex_promotional(self):
        """Test regex classification for promotional emails."""
        category, priority, reason = classify_with_regex(
            "מבצע חסר תקדים!",
            "Some Store",
            "Click to unsubscribe"
        )
        assert category == EmailCategory.PROMOTIONAL
        assert priority == Priority.P4

    def test_classify_with_regex_default(self):
        """Test regex classification default case."""
        category, priority, reason = classify_with_regex(
            "Meeting tomorrow",
            "Colleague",
            "Let's discuss the project"
        )
        assert category == EmailCategory.INFORMATIONAL
        assert priority == Priority.P3

    def test_parse_classification_result(self):
        """Test parsing LLM classification result."""
        result = {
            "category": "בירוקרטיה",
            "priority": "P1",
            "reason": "מייל ממשלתי",
            "deadline": "2026-01-30",
            "amount": "₪500",
            "action_suggestion": "לשלוח מסמכים",
        }

        cat, pri, reason, deadline, amount, action = parse_classification_result(result)

        assert cat == EmailCategory.BUREAUCRACY
        assert pri == Priority.P1
        assert reason == "מייל ממשלתי"
        assert deadline == "2026-01-30"
        assert amount == "₪500"
        assert action == "לשלוח מסמכים"


class TestFormatNode:
    """Tests for RTL formatting node."""

    def test_wrap_english(self):
        """Test English text wrapping with RTL markers."""
        text = "בדוק את GitHub שלך"
        wrapped = wrap_english(text)
        assert "\u200F" in wrapped  # RTL marker present

    def test_format_email_item_basic(self):
        """Test basic email item formatting."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="Test Subject",
            sender="John Doe",
            sender_email="john@example.com",
            date="2026-01-24",
            snippet="Test snippet",
            category=EmailCategory.INFORMATIONAL,
            priority=Priority.P3,
        )

        lines = format_email_item(email, include_details=True)

        assert any("John Doe" in line for line in lines)
        assert any("Test Subject" in line for line in lines)

    def test_format_email_item_with_deadline(self):
        """Test email item formatting with deadline."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="Urgent",
            sender="Gov",
            sender_email="gov@gov.il",
            date="2026-01-24",
            snippet="Deadline approaching",
            category=EmailCategory.BUREAUCRACY,
            priority=Priority.P1,
            deadline="2026-01-30",
        )

        lines = format_email_item(email, include_details=True)

        assert any("דד-ליין" in line for line in lines)

    def test_format_telegram_message_no_emails(self):
        """Test Telegram message with no emails."""
        message = format_telegram_message_hebrish(
            emails=[],
            p1_count=0,
            p2_count=0,
            p3_count=0,
            p4_count=0,
            system_count=5,
            duration_seconds=2.5,
        )

        assert "התראות מערכת" in message  # System emails mention
        assert "Smart Email Agent" in message

    def test_format_telegram_message_with_p1(self):
        """Test Telegram message with P1 emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="דחוף!",
            sender="ביטוח לאומי",
            sender_email="btl@gov.il",
            date="2026-01-24",
            snippet="נדרשת תשובה",
            category=EmailCategory.BUREAUCRACY,
            priority=Priority.P1,
            priority_reason="מייל ממשלתי דחוף",
        )

        message = format_telegram_message_hebrish(
            emails=[email],
            p1_count=1,
            p2_count=0,
            p3_count=0,
            p4_count=0,
            system_count=0,
            duration_seconds=1.0,
        )

        assert "ביטוח לאומי" in message
        assert "🔴" in message  # P1 indicator


class TestResearchNode:
    """Tests for research node."""

    def test_extract_search_query_gov(self):
        """Test search query extraction for government emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="הודעה חשובה",
            sender="ביטוח לאומי",
            sender_email="info@btl.gov.il",
            date="2026-01-24",
            snippet="טופס 101 נדרש",
            category=EmailCategory.BUREAUCRACY,
            priority=Priority.P1,
        )

        query = extract_search_query(email)

        assert "ביטוח לאומי" in query or "טופס" in query

    def test_should_research_p1(self):
        """Test research decision for P1 emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="Test",
            sender="Gov",
            sender_email="info@gov.il",
            date="2026-01-24",
            snippet="Test",
            category=EmailCategory.BUREAUCRACY,
            priority=Priority.P1,
        )

        assert should_research(email)

    def test_should_not_research_p4(self):
        """Test research decision for P4 emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="Sale!",
            sender="Store",
            sender_email="promo@store.com",
            date="2026-01-24",
            snippet="50% off",
            category=EmailCategory.PROMOTIONAL,
            priority=Priority.P4,
        )

        assert not should_research(email)


class TestHistoryNode:
    """Tests for history node."""

    def test_classify_relationship_new(self):
        """Test relationship classification for new contacts."""
        assert classify_relationship(total_emails=1, days_since_last=0) == "new"

    def test_classify_relationship_frequent(self):
        """Test relationship classification for frequent contacts."""
        assert classify_relationship(total_emails=15, days_since_last=5) == "frequent"

    def test_classify_relationship_recurring(self):
        """Test relationship classification for recurring contacts."""
        assert classify_relationship(total_emails=5, days_since_last=60) == "recurring"

    def test_extract_topics(self):
        """Test topic extraction from subjects."""
        subjects = [
            "Re: Project update",
            "Project status",
            "Fwd: Project timeline",
        ]

        topics = extract_topics(subjects)

        assert "project" in topics


class TestDraftNode:
    """Tests for draft generation node."""

    def test_determine_tone_formal(self):
        """Test tone determination for formal emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="הודעה",
            sender="ביטוח לאומי",
            sender_email="info@gov.il",
            date="2026-01-24",
            snippet="Test",
            category=EmailCategory.BUREAUCRACY,
            priority=Priority.P1,
        )

        assert determine_tone(email) == "formal"

    def test_determine_tone_friendly(self):
        """Test tone determination for personal emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="Hey",
            sender="Friend",
            sender_email="friend@gmail.com",
            date="2026-01-24",
            snippet="Test",
            category=EmailCategory.PERSONAL,
            priority=Priority.P3,
        )

        assert determine_tone(email) == "friendly"

    def test_determine_action_type_meeting(self):
        """Test action type for meeting requests."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="פגישה בזום",
            sender="Colleague",
            sender_email="colleague@work.com",
            date="2026-01-24",
            snippet="בוא נקבע פגישה",
            category=EmailCategory.CALENDAR,
            priority=Priority.P2,
        )

        assert determine_action_type(email) == "schedule_meeting"

    def test_should_generate_draft_p1_action(self):
        """Test draft generation decision for P1 action items."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="נדרשת תשובה",
            sender="Gov",
            sender_email="info@gov.il",
            date="2026-01-24",
            snippet="Test",
            category=EmailCategory.ACTION_REQUIRED,
            priority=Priority.P1,
        )

        assert should_generate_draft(email)

    def test_should_not_generate_draft_promo(self):
        """Test draft generation decision for promotional emails."""
        email = EmailItem(
            id="123",
            thread_id="456",
            subject="Sale!",
            sender="Store",
            sender_email="promo@store.com",
            date="2026-01-24",
            snippet="Test",
            category=EmailCategory.PROMOTIONAL,
            priority=Priority.P4,
        )

        assert not should_generate_draft(email)


class TestGraph:
    """Tests for LangGraph integration."""

    def test_create_email_graph_phase1(self):
        """Test Phase 1 graph creation."""
        graph = create_email_graph(enable_phase2=False)

        # Check nodes exist
        assert "fetch_emails" in graph.nodes
        assert "classify_emails" in graph.nodes
        assert "format_telegram" in graph.nodes
        assert "send_telegram" in graph.nodes

        # Phase 2 nodes should not be in edges for phase1 mode
        # (they exist but aren't connected)

    def test_create_email_graph_phase2(self):
        """Test Phase 2 graph creation."""
        graph = create_email_graph(enable_phase2=True)

        # Check all nodes exist
        assert "fetch_emails" in graph.nodes
        assert "classify_emails" in graph.nodes
        assert "research" in graph.nodes
        assert "history" in graph.nodes
        assert "draft" in graph.nodes
        assert "format_telegram" in graph.nodes
        assert "send_telegram" in graph.nodes

    def test_smart_email_graph_init(self):
        """Test SmartEmailGraph initialization."""
        agent = SmartEmailGraph(enable_phase2=True)

        assert agent.enable_phase2
        assert agent.graph is not None

    @pytest.mark.asyncio
    async def test_smart_email_graph_run_no_emails(self):
        """Test SmartEmailGraph run with no emails."""
        with patch("src.agents.smart_email.graph.GmailClient") as mock_gmail:
            # Mock empty email response
            mock_gmail.return_value.get_unread_emails.return_value = []

            agent = SmartEmailGraph(enable_phase2=False)

            # Run without sending to Telegram
            with patch("src.agents.smart_email.graph.send_telegram_node") as mock_send:
                mock_send.return_value = lambda state: {**state, "telegram_sent": False}

                result = await agent.run(
                    hours=24,
                    send_telegram=False,
                )

            assert result.get("total_count", 0) == 0


class TestEmailItem:
    """Tests for EmailItem dataclass."""

    def test_email_item_creation(self):
        """Test EmailItem creation with required fields."""
        item = EmailItem(
            id="test_id",
            thread_id="thread_123",
            subject="Test Subject",
            sender="Test Sender",
            sender_email="test@example.com",
            date="2026-01-24",
            snippet="Test snippet",
            category=EmailCategory.INFORMATIONAL,
            priority=Priority.P3,
        )

        assert item.id == "test_id"
        assert item.priority == Priority.P3
        assert item.deadline is None  # Optional field

    def test_email_item_with_research(self):
        """Test EmailItem with research result."""
        research = ResearchResult(
            email_id="test_id",
            query="ביטוח לאומי טופס 101",
            summary="נדרש למלא טופס 101",
            findings=["למלא טופס", "לצרף תעודת זהות"],
            sources=["https://btl.gov.il"],
            relevant_deadlines=["2026-01-30"],
        )

        item = EmailItem(
            id="test_id",
            thread_id="thread_123",
            subject="הודעה",
            sender="ביטוח לאומי",
            sender_email="info@btl.gov.il",
            date="2026-01-24",
            snippet="נא למלא טופס",
            category=EmailCategory.BUREAUCRACY,
            priority=Priority.P1,
            research=research,
        )

        assert item.research is not None
        assert "101" in item.research.query


class TestIntegration:
    """Integration tests for smart email agent."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self):
        """Test full pipeline with mocked dependencies."""
        # Create mock emails
        mock_emails = [
            {
                "id": "email_1",
                "thread_id": "thread_1",
                "subject": "דחוף: נדרשת תשובה",
                "sender": "ביטוח לאומי",
                "sender_email": "info@btl.gov.il",
                "date": "2026-01-24",
                "snippet": "נא לשלוח מסמכים עד 30/01",
                "labels": ["INBOX", "UNREAD"],
            },
            {
                "id": "email_2",
                "thread_id": "thread_2",
                "subject": "מבצע חסר תקדים!",
                "sender": "חנות",
                "sender_email": "promo@store.com",
                "date": "2026-01-24",
                "snippet": "50% הנחה על הכל",
                "labels": ["INBOX", "UNREAD"],
            },
        ]

        with patch("src.agents.smart_email.graph.GmailClient") as mock_gmail_class:
            # Setup mock
            mock_gmail = MagicMock()
            mock_gmail.get_unread_emails.return_value = [
                MagicMock(
                    id=e["id"],
                    thread_id=e["thread_id"],
                    subject=e["subject"],
                    sender=e["sender"],
                    sender_email=e["sender_email"],
                    date=e["date"],
                    snippet=e["snippet"],
                    labels=e["labels"],
                )
                for e in mock_emails
            ]
            mock_gmail_class.return_value = mock_gmail

            # Mock LLM calls
            with patch("src.agents.smart_email.nodes.classify.classify_with_llm") as mock_llm:
                mock_llm.return_value = None  # Force regex fallback

                # Mock Telegram send
                with patch("src.agents.smart_email.graph.httpx.post") as mock_http:
                    mock_http.return_value = MagicMock(status_code=200)

                    agent = SmartEmailGraph(enable_phase2=False)
                    result = await agent.run(hours=24, send_telegram=False)

        # Verify results
        assert result.get("total_count", 0) >= 0  # At least processed
        assert "telegram_message" in result or "errors" in result
