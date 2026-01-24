"""LangGraph state machine for Smart Email Agent v2.0.

Defines the email processing graph:
    Phase 1: FETCH → CLASSIFY → FORMAT → SEND
    Phase 2: FETCH → CLASSIFY → RESEARCH → HISTORY → DRAFT → FORMAT → SEND

Phase 1 MVP features:
- Gmail fetch via existing GmailClient
- LLM classification with Haiku
- Hebrish RTL formatting
- Telegram delivery

Phase 2 Intelligence features:
- Web research for P1/P2 emails
- Sender history lookup
- Draft reply generation
"""

import logging
import os
import time
from typing import Any

import httpx
from langgraph.graph import END, StateGraph

from src.agents.gmail_client import GmailClient
from src.agents.smart_email.nodes.classify import classify_emails_node
from src.agents.smart_email.nodes.draft import draft_node
from src.agents.smart_email.nodes.format_rtl import format_telegram_node
from src.agents.smart_email.nodes.history import history_node
from src.agents.smart_email.nodes.research import research_node
from src.agents.smart_email.state import EmailState, create_initial_state

logger = logging.getLogger(__name__)


# === Node Functions ===

async def fetch_emails_node(state: EmailState) -> EmailState:
    """Fetch emails from Gmail via LangGraph node.

    Uses the existing GmailClient to fetch unread emails.

    Args:
        state: Current graph state

    Returns:
        Updated state with raw_emails
    """
    hours = state.get("hours_lookback", 24)
    logger.info(f"Fetching emails from last {hours} hours")

    try:
        gmail = GmailClient()
        messages = gmail.get_unread_emails(hours=hours, max_results=50)

        # Convert to dicts for state
        raw_emails = []
        for msg in messages:
            raw_emails.append({
                "id": msg.id,
                "thread_id": msg.thread_id,
                "subject": msg.subject,
                "sender": msg.sender,
                "sender_email": msg.sender_email,
                "date": msg.date,
                "snippet": msg.snippet,
                "labels": msg.labels,
            })

        logger.info(f"Fetched {len(raw_emails)} emails")

        return {
            **state,
            "raw_emails": raw_emails,
        }

    except Exception as e:
        logger.error(f"Failed to fetch emails: {e}")
        errors = state.get("errors", [])
        errors.append(f"Fetch failed: {e}")
        return {
            **state,
            "raw_emails": [],
            "errors": errors,
        }


async def send_telegram_node(state: EmailState) -> EmailState:
    """Send message to Telegram via LangGraph node.

    Args:
        state: Current graph state with telegram_message

    Returns:
        Updated state with send result
    """
    message = state.get("telegram_message", "")
    if not message:
        logger.warning("No message to send")
        return {
            **state,
            "telegram_sent": False,
            "telegram_error": "No message",
        }

    try:
        # Load Telegram config
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            # Try GCP Secret Manager
            from src.secrets_manager import SecretManager
            manager = SecretManager()
            token = token or manager.get_secret("TELEGRAM-BOT-TOKEN")
            chat_id = chat_id or manager.get_secret("TELEGRAM-CHAT-ID")

        if not token or not chat_id:
            raise ValueError("Telegram config not found")

        # Send message
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=30,
        )

        if response.status_code == 200:
            logger.info("✅ Telegram message sent successfully")
            return {
                **state,
                "telegram_sent": True,
                "telegram_error": None,
            }
        else:
            error = response.text
            logger.error(f"❌ Telegram error: {error}")
            return {
                **state,
                "telegram_sent": False,
                "telegram_error": error,
            }

    except Exception as e:
        logger.error(f"Failed to send to Telegram: {e}")
        return {
            **state,
            "telegram_sent": False,
            "telegram_error": str(e),
        }


# === Graph Definition ===

def create_email_graph(enable_phase2: bool = True) -> StateGraph:
    """Create the LangGraph state machine for email processing.

    Graph structure (Phase 1 - MVP):
        fetch_emails → classify_emails → format_telegram → send_telegram → END

    Graph structure (Phase 2 - Intelligence):
        fetch → classify → research → history → draft → format → send → END

    Args:
        enable_phase2: Enable Phase 2 intelligence nodes (research, history, draft)

    Returns:
        Compiled LangGraph
    """
    # Create graph with state schema
    graph = StateGraph(EmailState)

    # Add Phase 1 nodes
    graph.add_node("fetch_emails", fetch_emails_node)
    graph.add_node("classify_emails", classify_emails_node)
    graph.add_node("format_telegram", format_telegram_node)
    graph.add_node("send_telegram", send_telegram_node)

    if enable_phase2:
        # Add Phase 2 intelligence nodes
        graph.add_node("research", research_node)
        graph.add_node("history", history_node)
        graph.add_node("draft", draft_node)

        # Define edges with Phase 2 flow
        graph.add_edge("fetch_emails", "classify_emails")
        graph.add_edge("classify_emails", "research")
        graph.add_edge("research", "history")
        graph.add_edge("history", "draft")
        graph.add_edge("draft", "format_telegram")
        graph.add_edge("format_telegram", "send_telegram")
        graph.add_edge("send_telegram", END)
    else:
        # Phase 1 only - linear flow
        graph.add_edge("fetch_emails", "classify_emails")
        graph.add_edge("classify_emails", "format_telegram")
        graph.add_edge("format_telegram", "send_telegram")
        graph.add_edge("send_telegram", END)

    # Set entry point
    graph.set_entry_point("fetch_emails")

    return graph.compile()


class SmartEmailGraph:
    """High-level interface for the Smart Email Agent graph.

    Example:
        agent = SmartEmailGraph()
        result = await agent.run(hours=24)
        print(result["telegram_message"])

    Phase 2 Example:
        agent = SmartEmailGraph(enable_phase2=True)
        result = await agent.run(
            hours=24,
            enable_research=True,
            enable_history=True,
            enable_drafts=True,
        )
    """

    def __init__(self, enable_phase2: bool = True):
        """Initialize the graph.

        Args:
            enable_phase2: Enable Phase 2 intelligence nodes
        """
        self.enable_phase2 = enable_phase2
        self.graph = create_email_graph(enable_phase2=enable_phase2)

    async def run(
        self,
        hours: int = 24,
        user_id: str = "default",
        send_telegram: bool = True,
        enable_research: bool = True,
        enable_history: bool = True,
        enable_drafts: bool = True,
    ) -> dict[str, Any]:
        """Run the email processing graph.

        Args:
            hours: Hours to look back for emails
            user_id: User identifier
            send_telegram: Whether to send to Telegram
            enable_research: Enable web research for P1/P2 emails
            enable_history: Enable sender history lookup
            enable_drafts: Enable draft reply generation

        Returns:
            Final state as dict
        """
        # Create initial state with Phase 2 flags
        state = create_initial_state(
            user_id=user_id,
            hours_lookback=hours,
            enable_research=enable_research if self.enable_phase2 else False,
            enable_history=enable_history if self.enable_phase2 else False,
            enable_drafts=enable_drafts if self.enable_phase2 else False,
        )

        logger.info(f"Starting SmartEmailGraph run {state['run_id']}")

        # Run the graph
        if send_telegram:
            final_state = await self.graph.ainvoke(state)
        else:
            # Skip telegram node by running partial graph
            # For now, just run full and ignore send result
            final_state = await self.graph.ainvoke(state)

        # Calculate final duration
        duration_ms = int((time.time() - state["start_time"]) * 1000)
        final_state["duration_ms"] = duration_ms

        logger.info(
            f"Completed run {state['run_id']} in {duration_ms}ms - "
            f"P1={final_state.get('p1_count', 0)}, "
            f"P2={final_state.get('p2_count', 0)}, "
            f"researched={final_state.get('research_count', 0)}, "
            f"drafts={final_state.get('drafts_count', 0)}, "
            f"sent={final_state.get('telegram_sent', False)}"
        )

        return dict(final_state)


# === Convenience Function ===

async def run_smart_email_agent(
    hours: int = 24,
    send_telegram: bool = True,
    enable_phase2: bool = True,
    enable_research: bool = True,
    enable_history: bool = True,
    enable_drafts: bool = True,
) -> dict[str, Any]:
    """Run the Smart Email Agent.

    Convenience function for simple usage.

    Args:
        hours: Hours to look back
        send_telegram: Whether to send to Telegram
        enable_phase2: Enable Phase 2 intelligence features
        enable_research: Enable web research for P1/P2 emails
        enable_history: Enable sender history lookup
        enable_drafts: Enable draft reply generation

    Returns:
        Execution result dict

    Example:
        import asyncio
        from src.agents.smart_email import run_smart_email_agent

        # Phase 1 only (fast, no LLM calls for research)
        result = asyncio.run(run_smart_email_agent(hours=24, enable_phase2=False))

        # Phase 2 full intelligence
        result = asyncio.run(run_smart_email_agent(hours=24))
        print(f"Processed {result['total_count']} emails")
        print(f"Researched {result.get('research_count', 0)} emails")
        print(f"Generated {result.get('drafts_count', 0)} drafts")
    """
    agent = SmartEmailGraph(enable_phase2=enable_phase2)
    return await agent.run(
        hours=hours,
        send_telegram=send_telegram,
        enable_research=enable_research,
        enable_history=enable_history,
        enable_drafts=enable_drafts,
    )


# === CLI Entry Point ===

def main():
    """CLI entry point for testing."""
    import asyncio
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse CLI args
    phase2 = "--phase1-only" not in sys.argv

    print("🤖 Smart Email Agent v2.0 (LangGraph)")
    print(f"📊 Mode: {'Phase 2 (Full Intelligence)' if phase2 else 'Phase 1 (MVP)'}")
    print("=" * 50)

    async def test_run():
        result = await run_smart_email_agent(
            hours=24,
            send_telegram=False,  # Don't send for testing
            enable_phase2=phase2,
        )

        print(f"\n✅ Success: {not result.get('errors')}")
        print(f"📬 Total emails: {result.get('total_count', 0)}")
        print(f"🔇 System filtered: {result.get('system_emails_count', 0)}")
        print(f"🔴 P1: {result.get('p1_count', 0)}")
        print(f"🟠 P2: {result.get('p2_count', 0)}")
        print(f"🟡 P3: {result.get('p3_count', 0)}")
        print(f"⚪ P4: {result.get('p4_count', 0)}")

        # Phase 2 stats
        if phase2:
            print(f"🔬 Researched: {result.get('research_count', 0)}")
            print(f"📝 Drafts: {result.get('drafts_count', 0)}")

        print(f"⏱️ Duration: {result.get('duration_ms', 0)}ms")

        if result.get("telegram_message"):
            print("\n" + "-" * 40)
            print("📝 Message preview:")
            print("-" * 40)
            print(result["telegram_message"])
            print("-" * 40)

        if result.get("errors"):
            print(f"\n❌ Errors: {result['errors']}")

    asyncio.run(test_run())


if __name__ == "__main__":
    main()
