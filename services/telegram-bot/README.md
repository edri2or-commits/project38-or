# Telegram Bot Service

**Multi-LLM Telegram bot using LiteLLM Gateway for intelligent routing**

## Overview

This service provides a Telegram bot interface that routes user requests through the LiteLLM Gateway, enabling access to multiple LLM providers (Claude, GPT-4, Gemini) with automatic fallback and cost optimization.

**Architecture:**
```
Telegram User
    ↓ (webhook)
Telegram Bot (FastAPI on Railway)
    ↓ (OpenAI-compatible API)
LiteLLM Gateway (https://litellm-gateway-production-0339.up.railway.app)
    ↓ (routing with fallback)
Claude 3.7 / GPT-4o / Gemini 1.5
    ↓ (MCP protocol for tool use)
MCP Gateway (Railway/n8n/Workspace operations)
```

## Features

- **Multi-LLM Support**: Access to Claude, GPT-4, and Gemini via LiteLLM Gateway
- **Automatic Fallback**: If primary model fails, automatically tries secondary models
- **Conversation History**: Maintains context with PostgreSQL storage
- **Cost Tracking**: Tracks token usage and estimated costs per user
- **FastAPI Backend**: High-performance async webhook receiver
- **Health Monitoring**: `/health` endpoint for Railway health checks
- **Security**: Secrets managed via GCP Secret Manager

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and available commands |
| `/generate <prompt>` | Generate a response for the given prompt |
| Regular message | Respond with conversation context |

## Configuration

### Environment Variables (Railway)

Required environment variables (set in Railway dashboard or via workflow):

| Variable | Purpose | Source |
|----------|---------|--------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | GCP Secret: `TELEGRAM-BOT-TOKEN` |
| `DATABASE_URL` | PostgreSQL connection string | Auto-provided by Railway |
| `TELEGRAM_WEBHOOK_URL` | Public URL of this service | Railway domain |
| `LITELLM_GATEWAY_URL` | LiteLLM Gateway endpoint | `https://litellm-gateway-production-0339.up.railway.app` |
| `GCP_PROJECT_ID` | GCP project for secrets | `project38-483612` |

Optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MODEL` | `claude-sonnet` | Default LLM model |
| `MAX_TOKENS` | `1000` | Max tokens per response |
| `MAX_CONVERSATION_HISTORY` | `10` | Messages to keep in context |
| `DEBUG` | `false` | Enable debug logging |

## Deployment

### Prerequisites

1. **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/botfather)
2. **Store Token in GCP**: Store bot token in GCP Secret Manager as `TELEGRAM-BOT-TOKEN`
3. **LiteLLM Gateway**: Ensure LiteLLM Gateway is deployed and accessible
4. **Railway Project**: Access to Railway project with PostgreSQL

### Railway Deployment

#### Option 1: GitHub Actions Workflow (Recommended)

```bash
# Run deployment workflow
gh workflow run deploy-telegram-bot.yml -f action=create-service --repo edri2or-commits/project38-or
gh workflow run deploy-telegram-bot.yml -f action=deploy --repo edri2or-commits/project38-or
```

#### Option 2: Manual Railway Deployment

1. **Create Railway Service**:
   ```bash
   railway service create telegram-bot
   railway service link telegram-bot
   ```

2. **Add PostgreSQL**:
   ```bash
   railway add --service postgresql
   ```

3. **Set Environment Variables** (via Railway Dashboard):
   - `TELEGRAM_BOT_TOKEN`: Get from GCP Secret Manager
   - `TELEGRAM_WEBHOOK_URL`: Will be set after first deployment
   - `LITELLM_GATEWAY_URL`: `https://litellm-gateway-production-0339.up.railway.app`
   - `GCP_PROJECT_ID`: `project38-483612`

4. **Deploy**:
   ```bash
   railway up --service telegram-bot
   ```

5. **Get Public URL**:
   ```bash
   railway domain --service telegram-bot
   # Example: https://telegram-bot-production-abcd.up.railway.app
   ```

6. **Setup Webhook**:
   ```bash
   curl -X POST https://telegram-bot-production-abcd.up.railway.app/webhook/setup
   ```

### Local Development

```bash
# Clone repository
cd services/telegram-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN=<your-bot-token>
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/telegrambot
export TELEGRAM_WEBHOOK_URL=https://your-ngrok-url.ngrok.io
export LITELLM_GATEWAY_URL=https://litellm-gateway-production-0339.up.railway.app

# Start PostgreSQL (Docker)
docker run --name telegram-bot-db -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15

# Run application
python main.py

# Or with uvicorn
uvicorn main:app --reload --port 8000

# Setup ngrok tunnel (for webhook)
ngrok http 8000

# Setup webhook
curl -X POST http://localhost:8000/webhook/setup
```

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service information |
| `/health` | GET | Health check (database, bot config) |
| `/webhook` | POST | Telegram webhook receiver |
| `/webhook/setup` | POST | Configure Telegram webhook |
| `/webhook/info` | GET | Get current webhook info |

### Health Check Response

```json
{
  "status": "healthy",
  "database": "connected",
  "bot_configured": true,
  "litellm_gateway": "https://litellm-gateway-production-0339.up.railway.app"
}
```

## Database Schema

### ConversationMessage

Stores individual messages:

```python
{
  "id": int,
  "chat_id": int,
  "user_id": int,
  "username": str | None,
  "role": str,  # "user" or "assistant"
  "content": str,
  "model": str | None,  # e.g., "claude-sonnet"
  "tokens_used": int | None,
  "created_at": datetime
}
```

### ConversationStats

Aggregated user statistics:

```python
{
  "id": int,
  "user_id": int,
  "username": str | None,
  "total_messages": int,
  "total_tokens": int,
  "total_cost_usd": float,
  "first_interaction": datetime,
  "last_interaction": datetime
}
```

## Usage Examples

### Basic Conversation

```
User: Hello!
Bot: Hello! How can I help you today?

User: What's the weather like?
Bot: [Response from Claude/GPT-4/Gemini via LiteLLM Gateway]
```

### Generate Command

```
User: /generate Write a haiku about coding
Bot: Code flows like water,
     Bugs dance in the moonlight,
     Deploy at sunrise.
```

### Conversation with Context

The bot maintains conversation history (last 10 messages by default), so follow-up questions work naturally:

```
User: What's 2+2?
Bot: 2+2 equals 4.

User: And if I multiply that by 3?
Bot: If you multiply 4 by 3, you get 12.
```

## Cost Tracking

The bot tracks token usage and estimates costs based on:
- Claude Sonnet: ~$9/1M tokens (average of input/output)
- GPT-4o: ~$6.25/1M tokens
- Gemini Pro: ~$3.12/1M tokens

View stats in database:
```sql
SELECT username, total_messages, total_tokens, total_cost_usd
FROM conversation_stats
ORDER BY total_cost_usd DESC;
```

## Monitoring

### Health Check

```bash
curl https://telegram-bot-production.railway.app/health
```

### Webhook Status

```bash
curl https://telegram-bot-production.railway.app/webhook/info
```

### Railway Logs

```bash
railway logs --service telegram-bot --tail
```

## Troubleshooting

### Issue: "Bot not responding"

**Cause**: Webhook not configured or incorrect URL.

**Fix**:
```bash
# Check webhook info
curl https://your-bot-url/webhook/info

# Reconfigure webhook
curl -X POST https://your-bot-url/webhook/setup
```

### Issue: "Database connection failed"

**Cause**: `DATABASE_URL` not set or PostgreSQL not running.

**Fix**:
- Railway: Ensure PostgreSQL service is linked
- Local: Start PostgreSQL container

### Issue: "LiteLLM Gateway timeout"

**Cause**: LiteLLM Gateway is down or unreachable.

**Fix**:
- Check Gateway status: `curl https://litellm-gateway-production-0339.up.railway.app/health`
- Verify `LITELLM_GATEWAY_URL` environment variable

### Issue: "Telegram bot token invalid"

**Cause**: `TELEGRAM_BOT_TOKEN` not set or incorrect.

**Fix**:
1. Verify token in GCP Secret Manager
2. Update Railway environment variable
3. Restart service

## Architecture Decisions

- **FastAPI + Webhook**: Faster than long polling, scales better
- **PostgreSQL**: Persistent conversation history, cost tracking
- **Async/Await**: Handle multiple users concurrently
- **LiteLLM Gateway**: Multi-provider routing with automatic fallback
- **GCP Secret Manager**: Secure token storage

## Security

### Best Practices

1. **Never hardcode tokens**: Use GCP Secret Manager
2. **HTTPS only**: Railway provides TLS automatically
3. **Webhook secret**: Consider adding webhook secret verification (future)
4. **Rate limiting**: Consider adding per-user rate limits (future)

### Secret Rotation

When rotating Telegram bot token:
1. Create new token via @BotFather
2. Update in GCP Secret Manager
3. Update Railway environment variable
4. Restart service
5. Reconfigure webhook

## Performance

- **Response time**: < 5s (depending on LLM)
- **Concurrent users**: 100+ (FastAPI + async)
- **Database connections**: Pool of 10 connections
- **Memory usage**: ~200MB baseline

## Testing

### End-to-End Test Plan

**Prerequisites:**
1. Telegram bot deployed to Railway
2. Public URL accessible: https://telegram-bot-production-053d.up.railway.app
3. Telegram app installed on your device
4. Bot username from @BotFather

### Phase 1: Service Health Verification

From a system with Railway access (outside Anthropic proxy):

```bash
# 1. Check service health
curl https://telegram-bot-production-053d.up.railway.app/health

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "bot_configured": true,
#   "litellm_gateway": "https://litellm-gateway-production-0339.up.railway.app"
# }

# 2. Check root endpoint
curl https://telegram-bot-production-053d.up.railway.app/

# Expected: JSON with service info

# 3. Verify webhook configuration
curl https://telegram-bot-production-053d.up.railway.app/webhook/info

# Expected: JSON with webhook URL and status
```

### Phase 2: Bot Interaction Testing

**Test Case 1: Start Command**
```
Action: Open Telegram, search for your bot, send: /start

Expected Response:
"Welcome to the Multi-LLM Bot! 🤖

Available commands:
/start - Show this message
/generate <prompt> - Generate a response

Or just send me any message and I'll respond with context!"

Verification:
✅ Bot responds within 5 seconds
✅ Message is clear and formatted correctly
```

**Test Case 2: Simple Message (No Context)**
```
Action: Send: "Hello!"

Expected Response:
A friendly greeting response from Claude/GPT-4/Gemini

Verification:
✅ Response is generated within 5 seconds
✅ Response is relevant and natural
✅ Check Railway logs for successful LiteLLM call
```

**Test Case 3: Generate Command**
```
Action: Send: /generate Write a haiku about coding

Expected Response:
A properly formatted haiku (3 lines: 5-7-5 syllables)

Verification:
✅ Response is a haiku
✅ Model used is logged (check Railway logs)
✅ Token usage recorded in database
```

**Test Case 4: Conversation with Context**
```
Action 1: Send: "What's 5 + 3?"
Expected: "5 + 3 equals 8." (or similar)

Action 2: Send: "And if I multiply that by 2?"
Expected: "If you multiply 8 by 2, you get 16." (or similar)

Verification:
✅ Bot remembers previous message (shows "8" not "5+3")
✅ Conversation context is maintained
✅ Database has both messages stored
```

**Test Case 5: Database Verification**

From Railway CLI or dashboard:
```sql
-- Check conversation messages
SELECT chat_id, user_id, username, role, content, model, tokens_used, created_at
FROM conversation_messages
ORDER BY created_at DESC
LIMIT 10;

-- Check user statistics
SELECT user_id, username, total_messages, total_tokens, total_cost_usd,
       first_interaction, last_interaction
FROM conversation_stats;

Verification:
✅ All messages are recorded
✅ Roles are correct (user/assistant)
✅ Model names are recorded (e.g., "claude-sonnet")
✅ Token counts are positive integers
✅ Cost estimates are calculated
✅ Timestamps are accurate
```

### Phase 3: LiteLLM Gateway Verification

**Test Case 6: Primary Model (Claude)**
```
Action: Send: "Tell me about yourself"

Expected: Response from Claude 3.7 Sonnet

Verification:
✅ Check Railway logs: Should show "model": "claude-sonnet"
✅ Response quality is high (Claude-level reasoning)
✅ Database records model as "claude-sonnet"
```

**Test Case 7: Fallback Mechanism (Optional)**

Requires temporarily revoking Claude API key:

```
1. Temporarily disable Claude in LiteLLM Gateway config
2. Send: "What's the capital of France?"
3. Expected: Response from GPT-4o (fallback)
4. Re-enable Claude

Verification:
✅ Bot still responds (doesn't fail)
✅ Railway logs show fallback model used
✅ User is unaware of backend change
```

### Phase 4: Cost Tracking

**Test Case 8: Token and Cost Tracking**
```
Action: Send 10 messages of varying lengths

Database Query:
SELECT user_id, username, total_messages, total_tokens, total_cost_usd
FROM conversation_stats
WHERE user_id = <your-telegram-user-id>;

Verification:
✅ total_messages = 10 (your messages) + N (bot responses)
✅ total_tokens > 0 and increasing
✅ total_cost_usd > 0 and matches token calculation
✅ Calculation: ~$9/1M tokens for Claude (average)
```

### Phase 5: Error Handling

**Test Case 9: Empty Message**
```
Action: Send empty message (if possible)

Expected: Either handled gracefully or prevented by Telegram

Verification:
✅ No crashes in Railway logs
✅ Database remains consistent
```

**Test Case 10: Very Long Message**
```
Action: Send message > 500 words

Expected: Response generated or gracefully truncated

Verification:
✅ Bot responds within timeout (< 30s)
✅ No memory issues
✅ Token limit respected (max 1000 by default)
```

### Success Criteria

**Deployment Success:**
- [x] Service deployed to Railway
- [x] Public domain accessible
- [x] PostgreSQL connected
- [x] Environment variables configured
- [x] Webhook configured

**Functional Success:**
- [ ] `/start` command works
- [ ] Simple messages generate responses
- [ ] `/generate` command works
- [ ] Conversation context maintained (2+ message exchanges)
- [ ] Database records all messages correctly
- [ ] Token usage tracked accurately
- [ ] Cost estimates calculated

**Integration Success:**
- [ ] LiteLLM Gateway responds (primary model)
- [ ] Fallback mechanism works (optional test)
- [ ] Claude/GPT-4/Gemini responses verified
- [ ] Response time < 5 seconds on average

**Performance Success:**
- [ ] Handles 10 consecutive messages without issues
- [ ] No memory leaks (check Railway metrics)
- [ ] Database connections stable
- [ ] No timeout errors

### Reporting Issues

If any test fails, collect:
1. **Test case number** that failed
2. **Expected vs. actual** behavior
3. **Railway logs** (last 50 lines): `railway logs --tail 50`
4. **Database state**: Query conversation_messages and conversation_stats
5. **Webhook info**: `curl https://telegram-bot-production-053d.up.railway.app/webhook/info`
6. **Health status**: `curl https://telegram-bot-production-053d.up.railway.app/health`

Report to GitHub Issue #242 with all diagnostic information.

## Future Enhancements

- [ ] Webhook secret verification
- [ ] Per-user rate limiting
- [ ] Admin commands (/stats, /users)
- [ ] Model selection command (/model claude-sonnet)
- [ ] Cost alerts per user
- [ ] Inline query support
- [ ] Group chat support
- [ ] Voice message transcription

## References

- **Telegram Bot API**: https://core.telegram.org/bots/api
- **python-telegram-bot**: https://docs.python-telegram-bot.org/
- **LiteLLM Gateway**: See `services/litellm-gateway/README.md`
- **Railway Docs**: https://docs.railway.app/

---

**Status**: ✅ Ready for Deployment
**Last Updated**: 2026-01-17
