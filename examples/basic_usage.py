"""
Basic APIBouncer Usage Example

Before running:
1. Launch the GUI: pythonw apibouncer_gui.pyw
2. Create a session with allowed models (e.g., gpt-image-1.5)
3. Copy your session ID
4. Replace SESSION_ID below with your actual session ID
"""

from apibouncer import openai, fal, query

# Replace with your actual session ID from the GUI
SESSION_ID = "APBN-XXXX-XXXXXXXXXXXX"


def example_openai_image():
    """Generate an image using OpenAI via APIBouncer."""
    print("Generating image via OpenAI...")

    try:
        result = openai.image(
            session_id=SESSION_ID,
            prompt="A serene mountain landscape at sunset",
            model="gpt-image-1.5",
            quality="low",  # Saves 10x compared to high
            size="1024x1536",
        )
        print(f"Success! Image saved to: {result['saved_to']}")
        return result
    except PermissionError as e:
        print(f"Blocked: {e}")
    except RuntimeError as e:
        print(f"API Error: {e}")


def example_fal_image():
    """Generate an image using fal.ai via APIBouncer."""
    print("Generating image via fal.ai...")

    try:
        result = fal.image(
            session_id=SESSION_ID,
            prompt="A serene mountain landscape at sunset",
            model="gpt-image-1.5",
            quality="low",
            size="1024x1024",
        )
        print(f"Success! Image saved to: {result['saved_to']}")
        return result
    except PermissionError as e:
        print(f"Blocked: {e}")
    except RuntimeError as e:
        print(f"API Error: {e}")


def example_check_budget():
    """Check remaining budget for a session."""
    print("Checking budget...")

    info = query.budget_remaining(SESSION_ID)

    if info.get("error"):
        print(f"Error: {info['error']}")
        return

    if info.get("unlimited"):
        print(f"No budget limit. Spent so far: ${info['spent']:.2f}")
    else:
        print(f"Budget: ${info['limit']:.2f}")
        print(f"Spent: ${info['spent']:.2f}")
        print(f"Remaining: ${info['remaining']:.2f}")
        print(f"Used: {info['percentage_used']:.1f}%")


def example_get_history():
    """Get recent request history for a session."""
    print("Getting recent history...")

    history = query.history(SESSION_ID, limit=5)

    if not history:
        print("No history yet")
        return

    for item in history:
        status = "OK" if item['status'] == 'allowed' else "BLOCKED"
        print(f"  [{status}] {item['provider']}/{item['model']} - ${item['cost']:.4f}")
        if item.get('reason'):
            print(f"         Reason: {item['reason']}")


if __name__ == "__main__":
    print("=" * 50)
    print("APIBouncer Example")
    print("=" * 50)
    print()

    # Check budget first
    example_check_budget()
    print()

    # Generate an image
    example_openai_image()
    print()

    # Check history
    example_get_history()
