"""Bot event handlers — auto-reply to messages, auto-match when liked,
and proactive first message after match creation."""
import asyncio
import logging
import random
import uuid

from sqlalchemy import select

from common.events import Event, event_bus
from db.models.user import User
from db.models.matching import Match
from db.models.chat import ChatMessage
from common.enums import MatchStatus
from app.config import settings

logger = logging.getLogger(__name__)


async def _on_bot_message_received(event: Event) -> None:
    """Handle message_received — if recipient is a bot, generate auto-reply."""
    payload = event.payload
    match_id = uuid.UUID(payload["match_id"])
    sender_user_id = uuid.UUID(payload["sender_user_id"])
    recipient_user_id = uuid.UUID(payload["recipient_user_id"])

    from db.session import async_session
    async with async_session() as db:
        try:
            # Load recipient
            recipient = await db.get(User, recipient_user_id)
            if not recipient or not recipient.is_bot:
                return  # Not a bot — nothing to do

            # Prevent bot-bot infinite loop
            sender = await db.get(User, sender_user_id)
            if sender and sender.is_bot:
                return  # Sender is also a bot, skip

            # Random delay so reply feels natural
            delay = random.uniform(
                settings.BOT_REPLY_DELAY_MIN, settings.BOT_REPLY_DELAY_MAX
            )
            logger.info(
                f"Bot {recipient_user_id} waiting {delay:.1f}s before replying "
                f"in match {match_id}"
            )
            await asyncio.sleep(delay)

            # Re-check: has the bot already replied to the latest human message?
            last_human = await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.match_id == match_id,
                    ChatMessage.sender_user_id != recipient_user_id,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            last_bot = await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.match_id == match_id,
                    ChatMessage.sender_user_id == recipient_user_id,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            human_msg = last_human.scalar_one_or_none()
            bot_msg = last_bot.scalar_one_or_none()
            if human_msg and bot_msg and bot_msg.created_at > human_msg.created_at:
                logger.info(
                    f"Bot {recipient_user_id} skipping reply in match {match_id}: "
                    f"already replied to latest human msg"
                )
                return
            logger.info(
                f"Bot {recipient_user_id} proceeding with reply in match {match_id}: "
                f"human_msg={human_msg.created_at if human_msg else None}, "
                f"bot_msg={bot_msg.created_at if bot_msg else None}"
            )

            # Verify match is still active
            match = await db.get(Match, match_id)
            if not match or match.status != MatchStatus.ACTIVE:
                return

            # Broadcast typing_started to chat WebSocket
            from modules.chat.websocket import broadcast_to_match
            await broadcast_to_match(match_id, recipient_user_id, {
                "event": "typing_started",
                "data": {"match_id": str(match_id), "user_id": str(recipient_user_id)},
            })

            # Generate reply via ADK BotAgent
            from modules.bot.bot_agent import generate_bot_reply
            logger.info(f"Bot {recipient_user_id} generating reply for match {match_id}")
            reply = await generate_bot_reply(db, recipient_user_id, match_id)

            # Broadcast typing_stopped
            await broadcast_to_match(match_id, recipient_user_id, {
                "event": "typing_stopped",
                "data": {"match_id": str(match_id), "user_id": str(recipient_user_id)},
            })

            if not reply:
                logger.warning(f"Bot {recipient_user_id} generated empty reply for match {match_id}")
                return  # LLM failed or no reply needed

            # Send reply via chat service
            from modules.chat.service import send_message
            await send_message(db, recipient_user_id, match_id, reply)
            logger.info(
                f"Bot {recipient_user_id} replied in match {match_id}: "
                f"{reply[:60]}..."
            )

        except Exception as e:
            logger.error(f"Bot message handler error: {e}")
            await db.rollback()


async def _on_bot_like_received(event: Event) -> None:
    """Handle like_received — if the liked user is a bot, auto-like back instantly."""
    payload = event.payload
    from_user_id = uuid.UUID(payload["from_user_id"])
    to_user_id = uuid.UUID(payload["to_user_id"])

    from db.session import async_session
    async with async_session() as db:
        try:
            # Check if to_user is a bot
            to_user = await db.get(User, to_user_id)
            if not to_user or not to_user.is_bot:
                return  # Not a bot — nothing to do

            # Prevent bot-bot auto-like loops: skip if from_user is also bot
            from_user = await db.get(User, from_user_id)
            if from_user and from_user.is_bot:
                return

            # Auto-like back instantly → creates mutual match
            from modules.matching.service import like_candidate
            result = await like_candidate(db, to_user_id, from_user_id)
            logger.info(
                f"Bot {to_user_id} auto-liked back {from_user_id}: "
                f"mutual={result.get('is_mutual')}"
            )

        except Exception as e:
            logger.error(f"Bot like handler error: {e}")
            await db.rollback()


async def _on_bot_match_created(event: Event) -> None:
    """Handle match_created — if a bot is in the new match, send icebreaker."""
    payload = event.payload
    match_id = uuid.UUID(payload["match_id"])
    user_a_id = uuid.UUID(payload["user_a_id"])
    user_b_id = uuid.UUID(payload["user_b_id"])

    from db.session import async_session
    async with async_session() as db:
        try:
            # Determine if one of the participants is a bot and the other is not
            user_a = await db.get(User, user_a_id)
            user_b = await db.get(User, user_b_id)
            if not user_a or not user_b:
                return

            bot_id = None
            if user_a.is_bot and not user_b.is_bot:
                bot_id = user_a_id
            elif user_b.is_bot and not user_a.is_bot:
                bot_id = user_b_id
            else:
                return  # Both bots or neither — skip

            # Random delay before first message
            delay = random.uniform(3.0, 10.0)
            logger.debug(
                f"Bot {bot_id} waiting {delay:.1f}s before icebreaker "
                f"in new match {match_id}"
            )
            await asyncio.sleep(delay)

            # Verify match is still active
            match = await db.get(Match, match_id)
            if not match or match.status != MatchStatus.ACTIVE:
                return

            # Check if there are already messages (someone beat us to it)
            existing_msg = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.match_id == match_id)
                .limit(1)
            )
            if existing_msg.scalar_one_or_none():
                return  # Conversation already started

            # Generate icebreaker via ADK BotAgent
            from modules.bot.bot_agent import generate_bot_reply
            reply = await generate_bot_reply(db, bot_id, match_id)
            if not reply:
                return

            # Send icebreaker
            from modules.chat.service import send_message
            await send_message(db, bot_id, match_id, reply)
            logger.info(
                f"Bot {bot_id} sent icebreaker in new match {match_id}: "
                f"{reply[:60]}..."
            )

        except Exception as e:
            logger.error(f"Bot match_created handler error: {e}")
            await db.rollback()


def register_bot_handlers() -> None:
    """Wire bot event handlers to the event bus. Called during app startup."""
    event_bus.on("message_received", _on_bot_message_received)
    event_bus.on("like_received", _on_bot_like_received)
    event_bus.on("match_created", _on_bot_match_created)
    logger.info("Bot event handlers registered (message_received, like_received, match_created)")
