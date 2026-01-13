# Project38-OR

> **Personal AI System** with autonomous GCP Secret Manager integration, Agent Factory, and Testing Harness.

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://edri2or-commits.github.io/project38-or/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Use secrets manager
from src.secrets_manager import SecretManager
manager = SecretManager()
api_key = manager.get_secret("ANTHROPIC-API")
```

**For detailed documentation**, see:
- 📖 **[Full Documentation](https://edri2or-commits.github.io/project38-or/)**
- 🏁 **[Getting Started Guide](https://edri2or-commits.github.io/project38-or/getting-started/)**
- 🔐 **[Security Policy](https://edri2or-commits.github.io/project38-or/SECURITY/)**
- 📚 **[API Reference](https://edri2or-commits.github.io/project38-or/api/)**

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **Agent Factory** | Generate autonomous AI agents from natural language descriptions |
| 🧪 **Testing Harness** | 24/7 execution with APScheduler + resource monitoring |
| 🔐 **Secret Management** | Autonomous GCP Secret Manager integration (zero secret exposure) |
| 🌐 **MCP Tools** | Browser automation (Playwright), filesystem, notifications (Telegram/n8n) |
| 🔄 **Auto-Merge Pipeline** | Autonomous PR validation and merging for `claude/` branches |
| 🚂 **Railway Deployment** | Production-ready FastAPI + PostgreSQL setup |

---

## 📦 Stack

- **Backend**: FastAPI + PostgreSQL (asyncpg, SQLModel)
- **AI**: Claude Sonnet 4.5 via Anthropic SDK
- **Secrets**: GCP Secret Manager (Workload Identity Federation)
- **CI/CD**: GitHub Actions with automated validation
- **Deployment**: Railway (ephemeral filesystem, persistent DB)

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Agent Factory  │ ──> Creates agents from natural language
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Testing Harness │ ──> Executes agents 24/7 with monitoring
└────────┬────────┘
         │
         v
┌─────────────────┐
│   MCP Tools     │ ──> Browser, filesystem, notifications
└─────────────────┘
```

See **[Architecture Guide](https://edri2or-commits.github.io/project38-or/BOOTSTRAP_PLAN/)** for details.

---

## 🛡️ Security

This is a **public repository**. Security rules:

- ✅ **Zero secrets in code** – all secrets via GCP Secret Manager
- ✅ **Zero secret exposure** – secrets never printed/logged
- ✅ **Memory-only storage** – secrets exist only in RAM
- ✅ **Workload Identity Federation** – no long-lived GitHub secrets

See **[SECURITY.md](https://edri2or-commits.github.io/project38-or/SECURITY/)** for full policy.

---

## 📚 Documentation

All documentation is at **[edri2or-commits.github.io/project38-or](https://edri2or-commits.github.io/project38-or/)**.

This README is intentionally minimal. For installation, usage, API references, and examples, see the full docs.

---

## 🤝 Contributing

See **[Contributing Guide](https://edri2or-commits.github.io/project38-or/development/contributing/)** in the documentation.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
