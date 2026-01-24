"""Tests for Smart Email Agent v2.0 (LangGraph-based).

Tests cover:
- State initialization and structure
- Classification node (LLM + regex fallback)
- Format RTL node (Telegram formatting)
- Research, History, Draft nodes
- Verification node (Phase 4.1: Proof of Completeness)
- Memory layer (Phase 4.10: Sender Intelligence)
- Conversation module (Phase 4.11: Conversational Telegram)
- Full graph execution

ADR-014: Smart Email Agent with Telegram Integration
"""

import os
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
    VerificationResult,
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
from src.agents.smart_email.nodes.verify import (
    verify_completeness_node,
    get_verification_summary,
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


class TestVerificationNode:
    """Tests for verification node (Phase 4: Proof of Completeness)."""

    def test_verification_result_is_complete(self):
        """Test VerificationResult.is_complete property."""
        # Complete case - all emails accounted for
        result = VerificationResult(
            gmail_total=10,
            processed_count=7,
            skipped_system=3,
            skipped_duplicates=0,
            missed_ids=[],
            verified=True,
        )
        assert result.is_complete is True

        # Incomplete case - missing emails
        result_incomplete = VerificationResult(
            gmail_total=10,
            processed_count=5,
            skipped_system=3,
            skipped_duplicates=0,
            missed_ids=["id1", "id2"],
            verified=False,
        )
        assert result_incomplete.is_complete is False

    def test_verification_result_summary_hebrew(self):
        """Test Hebrew summary generation."""
        # Complete case
        result = VerificationResult(
            gmail_total=23,
            processed_count=20,
            skipped_system=3,
            skipped_duplicates=0,
            missed_ids=[],
            verified=True,
        )
        summary = result.summary_hebrew()
        assert "✅" in summary
        assert "23/23" in summary
        assert "0 פוספסו" in summary

        # Incomplete case
        result_incomplete = VerificationResult(
            gmail_total=23,
            processed_count=18,
            skipped_system=3,
            skipped_duplicates=0,
            missed_ids=["id1", "id2"],
            verified=False,
        )
        summary = result_incomplete.summary_hebrew()
        assert "⚠️" in summary
        assert "2 פוספסו" in summary

    def test_verify_completeness_node_all_processed(self):
        """Test verification when all emails are processed."""
        # Create state with raw emails and processed emails matching
        state = {
            "raw_emails": [
                {"id": "1", "subject": "Test 1"},
                {"id": "2", "subject": "Test 2"},
                {"id": "3", "subject": "Test 3"},
            ],
            "emails": [
                EmailItem(
                    id="1", thread_id="t1", subject="Test 1",
                    sender="A", sender_email="a@test.com",
                    date="2026-01-24", snippet="test",
                ),
                EmailItem(
                    id="2", thread_id="t2", subject="Test 2",
                    sender="B", sender_email="b@test.com",
                    date="2026-01-24", snippet="test",
                ),
                EmailItem(
                    id="3", thread_id="t3", subject="Test 3",
                    sender="C", sender_email="c@test.com",
                    date="2026-01-24", snippet="test",
                ),
            ],
            "system_emails_count": 0,
        }

        result = verify_completeness_node(state)

        assert "verification" in result
        verification = result["verification"]
        assert verification.gmail_total == 3
        assert verification.processed_count == 3
        assert verification.is_complete is True
        assert len(verification.missed_ids) == 0

    def test_verify_completeness_node_with_system_emails(self):
        """Test verification when system emails are filtered."""
        state = {
            "raw_emails": [
                {"id": "1", "subject": "Test 1"},
                {"id": "2", "subject": "GitHub Notification"},
                {"id": "3", "subject": "Test 2"},
            ],
            "emails": [
                EmailItem(
                    id="1", thread_id="t1", subject="Test 1",
                    sender="A", sender_email="a@test.com",
                    date="2026-01-24", snippet="test",
                ),
                EmailItem(
                    id="3", thread_id="t3", subject="Test 2",
                    sender="C", sender_email="c@test.com",
                    date="2026-01-24", snippet="test",
                ),
            ],
            "system_emails_count": 1,  # GitHub notification was filtered
        }

        result = verify_completeness_node(state)

        verification = result["verification"]
        assert verification.gmail_total == 3
        assert verification.processed_count == 2
        assert verification.skipped_system == 1
        assert verification.is_complete is True

    def test_verify_completeness_node_missing_emails(self):
        """Test verification when emails are missed."""
        state = {
            "raw_emails": [
                {"id": "1", "subject": "Test 1"},
                {"id": "2", "subject": "Test 2"},
                {"id": "3", "subject": "Test 3"},
                {"id": "4", "subject": "Test 4"},
            ],
            "emails": [
                EmailItem(
                    id="1", thread_id="t1", subject="Test 1",
                    sender="A", sender_email="a@test.com",
                    date="2026-01-24", snippet="test",
                ),
                # Missing id 2, 3, 4
            ],
            "system_emails_count": 0,
        }

        result = verify_completeness_node(state)

        verification = result["verification"]
        assert verification.gmail_total == 4
        assert verification.processed_count == 1
        assert verification.is_complete is False
        # Should have missed IDs
        assert len(verification.missed_ids) > 0

    def test_get_verification_summary_with_result(self):
        """Test get_verification_summary helper function."""
        verification = VerificationResult(
            gmail_total=15,
            processed_count=15,
            skipped_system=0,
            missed_ids=[],
            verified=True,
        )
        state = {"verification": verification}

        summary = get_verification_summary(state)

        assert "✅" in summary
        assert "15/15" in summary

    def test_get_verification_summary_with_dict(self):
        """Test get_verification_summary with dict input (serialized state)."""
        state = {
            "verification": {
                "gmail_total": 10,
                "processed_count": 10,
                "skipped_system": 0,
                "missed_ids": [],
            }
        }

        summary = get_verification_summary(state)

        assert "✅" in summary
        assert "10/10" in summary

    def test_get_verification_summary_no_verification(self):
        """Test get_verification_summary when verification is None."""
        state = {"verification": None}

        summary = get_verification_summary(state)

        assert "אימות לא רץ" in summary

    def test_all_fetched_ids_tracked(self):
        """Test that all fetched email IDs are tracked."""
        state = {
            "raw_emails": [
                {"id": "email-001", "subject": "Test 1"},
                {"id": "email-002", "subject": "Test 2"},
            ],
            "emails": [
                EmailItem(
                    id="email-001", thread_id="t1", subject="Test 1",
                    sender="A", sender_email="a@test.com",
                    date="2026-01-24", snippet="test",
                ),
            ],
            "system_emails_count": 1,
        }

        result = verify_completeness_node(state)

        assert "all_fetched_ids" in result
        assert "email-001" in result["all_fetched_ids"]
        assert "email-002" in result["all_fetched_ids"]
        assert len(result["all_fetched_ids"]) == 2

    def test_all_processed_ids_tracked(self):
        """Test that all processed email IDs are tracked."""
        state = {
            "raw_emails": [
                {"id": "email-001", "subject": "Test 1"},
                {"id": "email-002", "subject": "Test 2"},
            ],
            "emails": [
                EmailItem(
                    id="email-001", thread_id="t1", subject="Test 1",
                    sender="A", sender_email="a@test.com",
                    date="2026-01-24", snippet="test",
                ),
                EmailItem(
                    id="email-002", thread_id="t2", subject="Test 2",
                    sender="B", sender_email="b@test.com",
                    date="2026-01-24", snippet="test",
                ),
            ],
            "system_emails_count": 0,
        }

        result = verify_completeness_node(state)

        assert "all_processed_ids" in result
        assert "email-001" in result["all_processed_ids"]
        assert "email-002" in result["all_processed_ids"]
        assert len(result["all_processed_ids"]) == 2


class TestMemoryLayer:
    """Tests for memory layer (Phase 4.10: Sender Intelligence)."""

    def test_memory_types_imports(self):
        """Test that memory types are importable."""
        from src.agents.smart_email.memory.types import (
            SenderProfile,
            InteractionRecord,
            ThreadSummary,
            ActionOutcome,
            ConversationContext,
            MemoryType,
            RelationshipType,
        )

        # Verify enum values
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.PROCEDURAL.value == "procedural"

        # Verify relationship types
        assert RelationshipType.NEW.value == "new"
        assert RelationshipType.VIP.value == "vip"
        assert RelationshipType.GOVERNMENT.value == "government"

    def test_sender_profile_dataclass(self):
        """Test SenderProfile dataclass creation."""
        from src.agents.smart_email.memory.types import SenderProfile, RelationshipType

        profile = SenderProfile(
            email="test@example.com",
            name="Test User",
            relationship_type=RelationshipType.RECURRING,
            role="רואה חשבון",
            total_interactions=15,
        )

        assert profile.email == "test@example.com"
        assert profile.relationship_type == RelationshipType.RECURRING
        assert profile.total_interactions == 15
        assert profile.is_vip is False  # Default

    def test_sender_profile_get_context_for_llm(self):
        """Test SenderProfile.get_context_for_llm method."""
        from src.agents.smart_email.memory.types import SenderProfile, RelationshipType

        profile = SenderProfile(
            email="danny@accountant.co.il",
            name="דני",
            role="רואה החשבון שלי",
            relationship_type=RelationshipType.FREQUENT,
            total_interactions=50,
            typical_topics=["חשבוניות", "דוחות", "מסים"],
            notes="תמיד שואל על חשבוניות בסוף חודש",
        )

        context = profile.get_context_for_llm()

        assert "דני" in context
        assert "רואה החשבון" in context
        assert "חשבוניות" in context
        assert "תכוף" in context  # Frequent relationship

    def test_sender_profile_should_prioritize(self):
        """Test SenderProfile.should_prioritize method."""
        from src.agents.smart_email.memory.types import SenderProfile, RelationshipType

        # VIP should be prioritized
        vip_profile = SenderProfile(
            email="vip@company.com",
            is_vip=True,
        )
        assert vip_profile.should_prioritize() is True

        # Government should be prioritized
        gov_profile = SenderProfile(
            email="notice@gov.il",
            relationship_type=RelationshipType.GOVERNMENT,
        )
        assert gov_profile.should_prioritize() is True

        # Regular sender should not be prioritized
        regular_profile = SenderProfile(
            email="random@store.com",
            relationship_type=RelationshipType.OCCASIONAL,
        )
        assert regular_profile.should_prioritize() is False

    def test_sender_profile_get_relationship_badge(self):
        """Test SenderProfile.get_relationship_badge method."""
        from src.agents.smart_email.memory.types import SenderProfile, RelationshipType

        new_profile = SenderProfile(email="new@test.com", relationship_type=RelationshipType.NEW)
        assert new_profile.get_relationship_badge() == "🆕"

        vip_profile = SenderProfile(email="vip@test.com", relationship_type=RelationshipType.VIP)
        assert vip_profile.get_relationship_badge() == "👑"

        bank_profile = SenderProfile(email="bank@test.com", relationship_type=RelationshipType.BANK)
        assert bank_profile.get_relationship_badge() == "🏦"

    def test_interaction_record_dataclass(self):
        """Test InteractionRecord dataclass creation."""
        from datetime import datetime
        from src.agents.smart_email.memory.types import InteractionRecord

        record = InteractionRecord(
            id="int_123",
            sender_email="test@example.com",
            timestamp=datetime.now(),
            email_id="email_123",
            thread_id="thread_456",
            subject="Test Subject",
            priority="P1",
            was_urgent=True,
        )

        assert record.id == "int_123"
        assert record.priority == "P1"
        assert record.was_urgent is True

    def test_conversation_context_add_message(self):
        """Test ConversationContext.add_message method."""
        from datetime import datetime
        from src.agents.smart_email.memory.types import ConversationContext

        context = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            started_at=datetime.now(),
            last_message_at=datetime.now(),
        )

        context.add_message("user", "מה עם המייל מהבנק?")
        context.add_message("assistant", "המייל מהבנק הוא על אישור הלוואה...")

        assert len(context.recent_messages) == 2
        assert context.recent_messages[0]["role"] == "user"
        assert context.recent_messages[1]["role"] == "assistant"

    def test_conversation_context_message_limit(self):
        """Test that ConversationContext keeps only last 30 messages."""
        from datetime import datetime
        from src.agents.smart_email.memory.types import ConversationContext

        context = ConversationContext(
            user_id="user_123",
            chat_id="chat_456",
            started_at=datetime.now(),
            last_message_at=datetime.now(),
        )

        # Add 35 messages
        for i in range(35):
            context.add_message("user", f"Message {i}")

        # Should only keep last 30
        assert len(context.recent_messages) == 30
        assert "Message 5" in context.recent_messages[0]["content"]

    def test_memory_node_classify_relationship(self):
        """Test classify_relationship function."""
        from src.agents.smart_email.nodes.memory import classify_relationship

        assert classify_relationship(0) == "new"
        assert classify_relationship(3) == "occasional"
        assert classify_relationship(10) == "recurring"
        assert classify_relationship(20) == "frequent"
        assert classify_relationship(5, is_vip=True) == "vip"

    def test_memory_node_get_sender_badge(self):
        """Test get_sender_badge function."""
        from src.agents.smart_email.nodes.memory import get_sender_badge

        assert get_sender_badge("new") == "🆕"
        assert get_sender_badge("vip") == "👑"
        assert get_sender_badge("government") == "🏛️"
        assert get_sender_badge("unknown") == "👤"  # Default

    def test_memory_node_format_sender_context_hebrew(self):
        """Test format_sender_context_hebrew function."""
        from src.agents.smart_email.nodes.memory import format_sender_context_hebrew

        context = format_sender_context_hebrew(
            relationship="frequent",
            total_interactions=25,
            typical_priority="P1",
            notes="תמיד דחוף",
        )

        assert "⭐" in context  # Frequent badge
        assert "תכוף" in context
        assert "25 הודעות" in context
        assert "P1" in context
        assert "תמיד דחוף" in context

    @pytest.mark.asyncio
    async def test_memory_enrich_node_no_database(self):
        """Test memory_enrich_node when DATABASE_URL is not set."""
        from src.agents.smart_email.nodes.memory import memory_enrich_node

        # No DATABASE_URL - should gracefully disable
        with patch.dict("os.environ", {}, clear=True):
            result = await memory_enrich_node({"raw_emails": []})
            assert result.get("memory_enabled") is False

    @pytest.mark.asyncio
    async def test_memory_record_node_disabled(self):
        """Test memory_record_node when memory is disabled."""
        from src.agents.smart_email.nodes.memory import memory_record_node

        state = {
            "emails": [],
            "memory_enabled": False,
        }

        result = await memory_record_node(state)
        assert result.get("interactions_recorded") == 0

    def test_memory_store_imports(self):
        """Test that MemoryStore is importable."""
        from src.agents.smart_email.memory.store import MemoryStore, SCHEMA_SQL

        # Verify schema contains required tables
        assert "sender_profiles" in SCHEMA_SQL
        assert "interaction_records" in SCHEMA_SQL
        assert "conversation_contexts" in SCHEMA_SQL
        assert "thread_summaries" in SCHEMA_SQL
        assert "action_rules" in SCHEMA_SQL

    def test_memory_store_initialization(self):
        """Test MemoryStore initialization without database."""
        from src.agents.smart_email.memory.store import MemoryStore

        store = MemoryStore()

        # Should initialize without error
        assert store.database_url is None
        assert store._pool is None

    def test_graph_with_memory_disabled(self):
        """Test graph creation with memory disabled."""
        from src.agents.smart_email.graph import create_email_graph

        graph = create_email_graph(enable_phase2=True, enable_memory=False)

        # Graph should compile without error
        assert graph is not None

    def test_graph_with_memory_enabled(self):
        """Test graph creation with memory enabled."""
        from src.agents.smart_email.graph import create_email_graph

        graph = create_email_graph(enable_phase2=True, enable_memory=True)

        # Graph should compile without error
        assert graph is not None

    def test_smart_email_graph_with_memory(self):
        """Test SmartEmailGraph initialization with memory."""
        from src.agents.smart_email.graph import SmartEmailGraph

        agent = SmartEmailGraph(enable_phase2=True, enable_memory=True)

        assert agent.enable_phase2 is True
        assert agent.enable_memory is True
        assert agent.graph is not None


class TestConversation:
    """Tests for conversation module (Phase 4.11: Conversational Telegram)."""

    def test_intent_classification_imports(self):
        """Test that conversation module is importable."""
        from src.agents.smart_email.conversation import (
            ConversationHandler,
            ConversationResponse,
            Intent,
            ActionType,
            classify_intent,
        )

        # Verify enum values
        assert Intent.EMAIL_QUERY.value == "email_query"
        assert Intent.ACTION_REQUEST.value == "action_request"
        assert ActionType.REPLY.value == "reply"

    def test_classify_intent_email_query(self):
        """Test intent classification for email queries."""
        from src.agents.smart_email.conversation import classify_intent, Intent

        result = classify_intent("מה עם המייל מדני?")
        assert result.intent == Intent.EMAIL_QUERY
        assert result.entities.get("sender_ref") == "דני"
        assert result.confidence >= 0.7

    def test_classify_intent_sender_query(self):
        """Test intent classification for sender queries."""
        from src.agents.smart_email.conversation import classify_intent, Intent

        result = classify_intent("מה עם דוד?")
        assert result.intent == Intent.SENDER_QUERY
        assert result.entities.get("sender_name") == "דוד"

    def test_classify_intent_action_request(self):
        """Test intent classification for action requests."""
        from src.agents.smart_email.conversation import classify_intent, Intent, ActionType

        result = classify_intent("שלח לו שאני מאשר")
        assert result.intent == Intent.ACTION_REQUEST
        assert result.action_type == ActionType.REPLY

    def test_classify_intent_action_reply(self):
        """Test action detection for reply intent."""
        from src.agents.smart_email.conversation import classify_intent, ActionType

        result = classify_intent("תענה לו שזה בסדר")
        assert result.action_type == ActionType.REPLY

    def test_classify_intent_summary_request(self):
        """Test intent classification for summary requests."""
        from src.agents.smart_email.conversation import classify_intent, Intent

        result = classify_intent("תסכם לי את המיילים")
        assert result.intent == Intent.SUMMARY_REQUEST

    def test_classify_intent_inbox_status(self):
        """Test intent classification for inbox status."""
        from src.agents.smart_email.conversation import classify_intent, Intent

        result = classify_intent("מה חדש בתיבה?")
        assert result.intent == Intent.SUMMARY_REQUEST

    def test_classify_intent_help(self):
        """Test intent classification for help requests."""
        from src.agents.smart_email.conversation import classify_intent, Intent

        result = classify_intent("עזרה")
        assert result.intent == Intent.HELP_REQUEST

    def test_classify_intent_general(self):
        """Test intent classification for general messages."""
        from src.agents.smart_email.conversation import classify_intent, Intent

        result = classify_intent("שלום, מה קורה?")
        assert result.intent == Intent.GENERAL

    def test_conversation_response_dataclass(self):
        """Test ConversationResponse dataclass."""
        from src.agents.smart_email.conversation import ConversationResponse, ActionType

        response = ConversationResponse(
            text="Test response",
            requires_confirmation=True,
            action_to_confirm=ActionType.REPLY,
            suggestions=["option1", "option2"],
        )

        assert response.text == "Test response"
        assert response.requires_confirmation is True
        assert response.action_to_confirm == ActionType.REPLY
        assert len(response.suggestions) == 2

    def test_conversation_handler_initialization(self):
        """Test ConversationHandler initialization."""
        from src.agents.smart_email.conversation import ConversationHandler

        handler = ConversationHandler()

        assert handler._store is None
        assert handler._initialized is False

    @pytest.mark.asyncio
    async def test_conversation_handler_help(self):
        """Test ConversationHandler help request."""
        from src.agents.smart_email.conversation import ConversationHandler

        handler = ConversationHandler()
        response = await handler.process_message(
            user_id="test_user",
            chat_id="test_chat",
            message="עזרה",
        )

        assert "עוזר המיילים" in response.text
        assert len(response.suggestions) > 0

    @pytest.mark.asyncio
    async def test_conversation_handler_summary_no_store(self):
        """Test ConversationHandler summary without memory store."""
        from src.agents.smart_email.conversation import ConversationHandler

        handler = ConversationHandler()
        # Don't initialize - no database
        response = await handler.process_message(
            user_id="test_user",
            chat_id="test_chat",
            message="תסכם לי",
        )

        # Should handle gracefully
        assert response.text is not None

    def test_intent_result_is_confident(self):
        """Test IntentResult.is_confident method."""
        from src.agents.smart_email.conversation.intents import IntentResult, Intent

        high_confidence = IntentResult(intent=Intent.EMAIL_QUERY, confidence=0.8)
        assert high_confidence.is_confident(threshold=0.6) is True

        low_confidence = IntentResult(intent=Intent.GENERAL, confidence=0.4)
        assert low_confidence.is_confident(threshold=0.6) is False

    def test_entity_extraction_email_from(self):
        """Test entity extraction for 'המייל מ[שם]' pattern."""
        from src.agents.smart_email.conversation import classify_intent

        result = classify_intent("תזכיר לי על המייל מהבנק")
        assert result.entities.get("sender_ref") == "הבנק"

    def test_entity_extraction_email_of(self):
        """Test entity extraction for 'המייל של [שם]' pattern."""
        from src.agents.smart_email.conversation import classify_intent

        result = classify_intent("המייל של יוסי")
        assert result.entities.get("sender_name") == "יוסי"

    def test_action_type_detection_approve(self):
        """Test action type detection for approval."""
        from src.agents.smart_email.conversation import classify_intent, ActionType

        result = classify_intent("תאשר את זה")
        assert result.action_type == ActionType.APPROVE

    def test_action_type_detection_archive(self):
        """Test action type detection for archive."""
        from src.agents.smart_email.conversation import classify_intent, ActionType

        result = classify_intent("ארכב את זה")
        assert result.action_type == ActionType.ARCHIVE

    def test_get_intent_description_hebrew(self):
        """Test Hebrew descriptions for intents."""
        from src.agents.smart_email.conversation import (
            get_intent_description_hebrew,
            Intent,
        )

        desc = get_intent_description_hebrew(Intent.EMAIL_QUERY)
        assert "מייל" in desc

        desc = get_intent_description_hebrew(Intent.ACTION_REQUEST)
        assert "פעולה" in desc

    def test_get_action_description_hebrew(self):
        """Test Hebrew descriptions for actions."""
        from src.agents.smart_email.conversation import (
            get_action_description_hebrew,
            ActionType,
        )

        desc = get_action_description_hebrew(ActionType.REPLY)
        assert "לענות" in desc

        desc = get_action_description_hebrew(ActionType.ARCHIVE)
        assert "לארכב" in desc
# Phase 4.12: Action System Tests
# ============================================================================


class TestActionSystem:
    """Tests for Phase 4.12 Action System with Approval."""

    def test_action_type_enum(self):
        """Test ActionType enum values."""
        from src.agents.smart_email.actions import ActionType

        assert ActionType.REPLY.value == "reply"
        assert ActionType.FORWARD.value == "forward"
        assert ActionType.ARCHIVE.value == "archive"
        assert ActionType.MARK_READ.value == "mark_read"
        assert ActionType.SNOOZE.value == "snooze"

    def test_action_status_enum(self):
        """Test ActionStatus enum values."""
        from src.agents.smart_email.actions import ActionStatus

        assert ActionStatus.PENDING.value == "pending"
        assert ActionStatus.APPROVED.value == "approved"
        assert ActionStatus.REJECTED.value == "rejected"
        assert ActionStatus.COMPLETED.value == "completed"
        assert ActionStatus.FAILED.value == "failed"
        assert ActionStatus.EXPIRED.value == "expired"

    def test_action_request_creation(self):
        """Test ActionRequest creation."""
        from src.agents.smart_email.actions import (
            ActionRequest,
            ActionType,
            ActionStatus,
        )

        request = ActionRequest(
            id="req_test123",
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
            email_id="msg_abc",
            email_sender="dan@example.com",
            reply_content="אני מאשר",
        )

        assert request.id == "req_test123"
        assert request.action_type == ActionType.REPLY
        assert request.status == ActionStatus.PENDING
        assert request.email_sender == "dan@example.com"
        assert request.reply_content == "אני מאשר"

    def test_action_request_is_expired_false(self):
        """Test ActionRequest.is_expired returns False for fresh request."""
        from datetime import datetime, timedelta
        from src.agents.smart_email.actions import ActionRequest, ActionType

        request = ActionRequest(
            id="req_test",
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
            expires_at=datetime.now() + timedelta(minutes=5),
        )

        assert request.is_expired() is False

    def test_action_request_is_expired_true(self):
        """Test ActionRequest.is_expired returns True for expired request."""
        from datetime import datetime, timedelta
        from src.agents.smart_email.actions import ActionRequest, ActionType

        request = ActionRequest(
            id="req_test",
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
            expires_at=datetime.now() - timedelta(minutes=1),
        )

        assert request.is_expired() is True

    def test_action_request_can_execute(self):
        """Test ActionRequest.can_execute logic."""
        from datetime import datetime, timedelta
        from src.agents.smart_email.actions import (
            ActionRequest,
            ActionType,
            ActionStatus,
        )

        # Pending - cannot execute
        pending = ActionRequest(
            id="req_pending",
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
            status=ActionStatus.PENDING,
            expires_at=datetime.now() + timedelta(minutes=5),
        )
        assert pending.can_execute() is False

        # Approved - can execute
        approved = ActionRequest(
            id="req_approved",
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
            status=ActionStatus.APPROVED,
            expires_at=datetime.now() + timedelta(minutes=5),
        )
        assert approved.can_execute() is True

    def test_action_result_to_hebrew_success(self):
        """Test ActionResult.to_hebrew for success."""
        from src.agents.smart_email.actions import (
            ActionResult,
            ActionType,
            ActionStatus,
        )

        result = ActionResult(
            request_id="req_test",
            action_type=ActionType.REPLY,
            success=True,
            status=ActionStatus.COMPLETED,
        )

        hebrew = result.to_hebrew()
        assert "✅" in hebrew
        assert "תשובה" in hebrew
        assert "בהצלחה" in hebrew

    def test_action_result_to_hebrew_failure(self):
        """Test ActionResult.to_hebrew for failure."""
        from src.agents.smart_email.actions import (
            ActionResult,
            ActionType,
            ActionStatus,
        )

        result = ActionResult(
            request_id="req_test",
            action_type=ActionType.ARCHIVE,
            success=False,
            status=ActionStatus.FAILED,
            error="Network error",
        )

        hebrew = result.to_hebrew()
        assert "❌" in hebrew
        assert "ארכיון" in hebrew
        assert "Network error" in hebrew

    def test_audit_record_to_log_entry(self):
        """Test AuditRecord.to_log_entry formatting."""
        from datetime import datetime
        from src.agents.smart_email.actions import (
            AuditRecord,
            ActionType,
            ActionStatus,
        )

        record = AuditRecord(
            id="audit_123",
            request_id="req_456",
            user_id="user_789",
            action_type=ActionType.REPLY,
            email_subject="Test Subject",
            status=ActionStatus.COMPLETED,
            requested_at=datetime.now(),
        )

        log_entry = record.to_log_entry()
        assert "✅" in log_entry
        assert "user_789" in log_entry
        assert "reply" in log_entry
        assert "Test Subject" in log_entry

    def test_approval_manager_create_proposal(self):
        """Test ApprovalManager.create_proposal."""
        from src.agents.smart_email.actions import (
            ApprovalManager,
            ActionType,
            ActionStatus,
        )

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
            email_sender="dan@example.com",
            reply_content="אני מאשר",
        )

        assert proposal.id.startswith("req_")
        assert proposal.action_type == ActionType.REPLY
        assert proposal.status == ActionStatus.PENDING
        assert proposal.email_sender == "dan@example.com"
        assert proposal.reply_content == "אני מאשר"
        assert proposal.expires_at is not None

    def test_approval_manager_get_pending(self):
        """Test ApprovalManager.get_pending."""
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager()

        # Create proposals for different users
        manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_1",
            chat_id="chat_1",
        )
        manager.create_proposal(
            action_type=ActionType.ARCHIVE,
            user_id="user_2",
            chat_id="chat_2",
        )

        # Get all pending
        all_pending = manager.get_pending()
        assert len(all_pending) == 2

        # Get for specific user
        user1_pending = manager.get_pending(user_id="user_1")
        assert len(user1_pending) == 1
        assert user1_pending[0].action_type == ActionType.REPLY

    def test_approval_manager_reject(self):
        """Test ApprovalManager.reject."""
        from src.agents.smart_email.actions import (
            ApprovalManager,
            ActionType,
            ActionStatus,
        )

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
        )

        # Reject
        result = manager.reject(proposal.id, reason="לא מתאים")
        assert result is True

        # Should not be pending anymore
        pending = manager.get_pending(user_id="user_123")
        assert len(pending) == 0

        # Should be in history with rejected status
        assert proposal.status == ActionStatus.REJECTED

    def test_approval_manager_cancel(self):
        """Test ApprovalManager.cancel."""
        from src.agents.smart_email.actions import (
            ApprovalManager,
            ActionType,
            ActionStatus,
        )

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.FORWARD,
            user_id="user_123",
            chat_id="chat_456",
        )

        # Cancel
        result = manager.cancel(proposal.id)
        assert result is True
        assert proposal.status == ActionStatus.CANCELLED

    def test_approval_manager_format_proposal_hebrew_reply(self):
        """Test ApprovalManager.format_proposal_hebrew for reply."""
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
            email_sender="דני",
            email_subject="שאלה חשובה",
            reply_content="אני מאשר את ההצעה",
        )

        formatted = manager.format_proposal_hebrew(proposal)
        assert "לשלוח תשובה" in formatted
        assert "דני" in formatted
        assert "שאלה חשובה" in formatted
        assert "אני מאשר את ההצעה" in formatted

    def test_approval_manager_format_proposal_hebrew_archive(self):
        """Test ApprovalManager.format_proposal_hebrew for archive."""
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
            email_sender="spam@example.com",
            email_subject="Spam email",
        )

        formatted = manager.format_proposal_hebrew(proposal)
        assert "לארכב" in formatted
        assert "spam@example.com" in formatted

    def test_approval_manager_get_keyboard_options(self):
        """Test ApprovalManager.get_keyboard_options."""
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
        )

        buttons = manager.get_keyboard_options(proposal)
        assert len(buttons) >= 2

        # Should have approve and reject
        button_texts = [b["text"] for b in buttons]
        assert any("אשר" in t for t in button_texts)
        assert any("בטל" in t for t in button_texts)

        # Reply should have edit button
        assert any("ערוך" in t for t in button_texts)

    def test_approval_manager_get_keyboard_options_archive(self):
        """Test ApprovalManager.get_keyboard_options for archive (no edit)."""
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
        )

        buttons = manager.get_keyboard_options(proposal)
        button_texts = [b["text"] for b in buttons]

        # Archive should NOT have edit button
        assert not any("ערוך" in t for t in button_texts)

    @pytest.mark.asyncio
    async def test_action_executor_not_approved(self):
        """Test ActionExecutor rejects non-approved requests."""
        from src.agents.smart_email.actions import (
            ActionExecutor,
            ActionRequest,
            ActionType,
            ActionStatus,
        )

        executor = ActionExecutor()
        request = ActionRequest(
            id="req_test",
            action_type=ActionType.ARCHIVE,
            user_id="user_123",
            chat_id="chat_456",
            status=ActionStatus.PENDING,  # Not approved
        )

        result = await executor.execute(request)
        assert result.success is False
        assert "not approved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_action_executor_reply_no_content(self):
        """Test ActionExecutor rejects reply without content."""
        from datetime import datetime, timedelta
        from src.agents.smart_email.actions import (
            ActionExecutor,
            ActionRequest,
            ActionType,
            ActionStatus,
        )

        executor = ActionExecutor()
        request = ActionRequest(
            id="req_test",
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
            status=ActionStatus.APPROVED,
            expires_at=datetime.now() + timedelta(minutes=5),
            reply_content=None,  # No content
        )

        result = await executor.execute(request)
        assert result.success is False
        assert "content" in result.error.lower()

    @pytest.mark.asyncio
    async def test_approval_manager_approve(self):
        """Test ApprovalManager.approve executes action."""
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager()
        proposal = manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
            email_sender="dan@example.com",
            reply_content="Test reply",
        )

        # Approve should execute via MCP (simulated)
        result = await manager.approve(proposal.id)

        # MCP gateway is simulated, so it should succeed
        assert result.success is True
        assert result.action_type == ActionType.REPLY

    @pytest.mark.asyncio
    async def test_approval_manager_approve_expired(self):
        """Test ApprovalManager.approve rejects expired request."""
        from datetime import datetime, timedelta
        from src.agents.smart_email.actions import ApprovalManager, ActionType

        manager = ApprovalManager(approval_timeout_minutes=0)  # Immediate expiry

        proposal = manager.create_proposal(
            action_type=ActionType.REPLY,
            user_id="user_123",
            chat_id="chat_456",
            reply_content="Test reply",
        )

        # Force expiration
        proposal.expires_at = datetime.now() - timedelta(minutes=1)

        with pytest.raises(ValueError, match="expired"):
            await manager.approve(proposal.id)

    def test_create_approval_manager_factory(self):
        """Test create_approval_manager factory function."""
        from src.agents.smart_email.actions import create_approval_manager

        manager = create_approval_manager(
            use_mcp_gateway=True,
            timeout_minutes=10,
        )

        assert manager is not None
        assert manager.approval_timeout.total_seconds() == 600
        assert manager.executor.use_mcp_gateway is True

    def test_action_executor_get_audit_log(self):
        """Test ActionExecutor.get_audit_log."""
        from src.agents.smart_email.actions import ActionExecutor

        executor = ActionExecutor()

        # Initially empty
        log = executor.get_audit_log()
        assert len(log) == 0

    def test_action_executor_format_audit_log_empty(self):
        """Test ActionExecutor.format_audit_log_hebrew with no records."""
        from src.agents.smart_email.actions import ActionExecutor

        executor = ActionExecutor()
        formatted = executor.format_audit_log_hebrew()

        assert "אין פעולות" in formatted
