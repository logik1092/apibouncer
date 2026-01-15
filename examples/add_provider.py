"""
Example: Adding a new provider to APIBouncer

This shows how to add Replicate as a provider.
Copy this pattern for any API.
"""

import requests
from apibouncer.proxy import BaseProvider

class Replicate(BaseProvider):
    """Replicate.com API provider."""

    PROVIDER_NAME = "replicate"  # Used for API key lookup and logging

    # Cost per model (used for budget tracking)
    DEFAULT_COSTS = {
        "stability-ai/sdxl": 0.01,
        "black-forest-labs/flux-schnell": 0.003,
        "black-forest-labs/flux-dev": 0.025,
    }

    def run(self, session_id: str, model: str, prompt: str, **kwargs):
        """Run a model on Replicate."""

        # 1. Get cost estimate
        cost = self.get_cost(model)

        # 2. Build params for logging
        params = {"prompt": prompt, "model": model, **kwargs}

        # 3. Validate (checks session, model whitelist, budget, rate limit)
        #    Raises PermissionError if blocked
        self.validate(session_id, model, cost, params)

        # 4. Get API key (from Windows Credential Manager)
        api_key = self.get_key()

        # 5. Make API call
        try:
            response = requests.post(
                f"https://api.replicate.com/v1/predictions",
                headers={"Authorization": f"Token {api_key}"},
                json={"version": model, "input": {"prompt": prompt, **kwargs}},
                timeout=60
            )

            if response.status_code != 201:
                self.record_error(session_id, model, f"API error: {response.status_code}")
                raise RuntimeError(f"Replicate error: {response.text}")

            data = response.json()

            # 6. Record success
            self.record_success(session_id, model, cost, params, response_data=data)

            return data

        except requests.RequestException as e:
            self.record_error(session_id, model, f"Network error: {e}")
            raise


# Create instance for easy importing
replicate = Replicate()


# Usage:
# from examples.add_provider import replicate
#
# result = replicate.run(
#     session_id="APBN-XXXX-XXXX",
#     model="stability-ai/sdxl",
#     prompt="A cat in space"
# )
"""

That's it! The BaseProvider handles:
- API key retrieval from secure storage
- Session validation
- Model whitelist checking
- Budget enforcement
- Rate limiting
- Request logging
- Error recording

You just write the API-specific code.
"""
