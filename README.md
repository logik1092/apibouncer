# APIBouncer

**Protect yourself from costly API mistakes.**

Block unapproved models, enforce cost limits, and track your savings. Built for developers using OpenAI, fal.ai, MiniMax, and other AI APIs.

## The Problem

AI agents and scripts can rack up huge bills by:
- Using expensive models you didn't approve
- Generating high-quality images when low would suffice
- Making unlimited requests without rate limits
- Exceeding budgets with no safeguards

## The Solution

APIBouncer sits between your code and the API:

```python
from apibouncer import openai

# Your AI agent calls this - never sees the API key
result = openai.image(
    session_id="APBN-XXXX-XXXXXXXXXXXX",  # Your session ID
    prompt="A landscape photo",
    model="gpt-image-1.5",
    quality="low",  # Enforced by your rules
)
```

You control:
- **Which models** are allowed (whitelist/blacklist)
- **Quality settings** (force "low" to save 10x)
- **Budget limits** (hard cap per session)
- **Rate limits** (requests per hour)
- **Provider restrictions** (OpenAI only, fal.ai only, etc.)

## Features

- **Session-based access control** - Create isolated sessions for different projects/agents
- **Model whitelisting** - Only approved models can be used
- **Quality enforcement** - Force low-quality image generation (saves 10x on OpenAI)
- **Budget caps** - Set spending limits per session
- **Rate limiting** - Prevent runaway scripts
- **Multi-provider support** - OpenAI, fal.ai, MiniMax
- **Smart routing** - Auto-select cheapest provider for your use case
- **Request history** - Full audit trail with images
- **Panic mode** - Instantly block ALL API calls
- **GUI dashboard** - Visual management of all settings

## Installation

```bash
pip install keyring requests
```

For the GUI:
```bash
pip install pillow pystray plyer  # Optional but recommended
```

## Quick Start

### 1. Store your API keys (one-time setup)

```python
import keyring

keyring.set_password("apibouncer", "openai", "sk-...")
keyring.set_password("apibouncer", "fal", "your-fal-key")
keyring.set_password("apibouncer", "minimax", "your-minimax-key")
```

### 2. Launch the GUI

```bash
pythonw apibouncer_gui.pyw
```

### 3. Create a session

In the GUI:
1. Go to Sessions tab
2. Click "New Session"
3. Set allowed models (e.g., `gpt-image-1.5`)
4. Set quality restrictions (e.g., only `low`)
5. Set budget limit
6. Copy the session ID

### 4. Use in your code

```python
from apibouncer import openai

# Generate an image (API key is never exposed)
result = openai.image(
    session_id="APBN-XXXX-XXXXXXXXXXXX",
    prompt="A mountain landscape",
    model="gpt-image-1.5",
    quality="low",
    size="1024x1536",
)

print(f"Saved to: {result['saved_to']}")
```

## Providers

### OpenAI

```python
from apibouncer import openai

# Image generation
result = openai.image(
    session_id="...",
    prompt="...",
    model="gpt-image-1.5",
    quality="low",  # low/medium/high
    size="1024x1536",
)

# Chat completion
result = openai.chat(
    session_id="...",
    messages=[{"role": "user", "content": "Hello"}],
    model="gpt-4o-mini",
)
```

### fal.ai

```python
from apibouncer import fal

# Image generation (cheaper for some models)
result = fal.image(
    session_id="...",
    prompt="...",
    model="gpt-image-1.5",  # or flux-dev, flux-schnell, etc.
    quality="low",
    size="1024x1024",
)

# With reference images (image-to-image)
result = fal.image(
    session_id="...",
    prompt="...",
    reference_images=["path/to/image.png"],
    model="flux-dev-image-to-image",
)
```

### MiniMax (Video)

```python
from apibouncer import minimax

result = minimax.video(
    session_id="...",
    prompt="A cat walking",
    model="video-01",
)
```

## Query API (Read-Only)

AI agents can query session info without modification access:

```python
from apibouncer import query

# Check budget
info = query.budget_remaining("APBN-XXXX-...")
print(f"Remaining: ${info['remaining']:.2f}")

# Get session info
info = query.session_info("APBN-XXXX-...")

# Get history
history = query.history("APBN-XXXX-...", limit=10)

# Get prices
prices = query.prices()
```

## Security Model

1. **API keys stored in OS keyring** - Never in code or config files
2. **Session IDs are secrets** - Treat like passwords, don't commit to repos
3. **AI never sees keys** - Proxy injects keys internally
4. **All requests validated** - Model, quality, budget, rate checked before API call
5. **Audit trail** - Every request logged with full details

## Pricing Reference

### OpenAI (direct)
| Model | Low | Medium | High |
|-------|-----|--------|------|
| gpt-image-1.5 | $0.02 | $0.07 | $0.20 |

### fal.ai (often cheaper)
| Model | Low | Medium | High |
|-------|-----|--------|------|
| gpt-image-1.5 | $0.013 | $0.051 | $0.17 |
| flux-schnell | $0.003 | - | - |
| flux-dev | $0.025 | - | - |

## License

MIT License - see LICENSE file.
