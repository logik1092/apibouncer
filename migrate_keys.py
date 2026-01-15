"""
Migrate API keys from Windows Credential Manager (keyring) to encrypted local storage.

This script:
1. Reads all APIBouncer keys from keyring
2. Stores them in the new encrypted keystore
3. Deletes them from keyring (so AI can't access via keyring.get_password)

Run this once after updating APIBouncer to secure your keys.
"""

import sys
sys.path.insert(0, ".")

print("=" * 50)
print("APIBouncer Key Migration")
print("=" * 50)

try:
    import keyring
except ImportError:
    print("\n[!] keyring not installed - nothing to migrate")
    sys.exit(0)

try:
    from apibouncer.keystore import get_keystore
except ImportError:
    print("\n[!] cryptography not installed. Run: pip install cryptography")
    sys.exit(1)

SERVICE_NAME = "apibouncer"

# Known provider IDs
PROVIDERS = ["openai", "anthropic", "fal", "minimax"]

print("\nChecking for keys in Windows Credential Manager...")

keystore = get_keystore()
migrated = 0
already_secure = 0

for provider in PROVIDERS:
    # Check keyring
    keyring_key = keyring.get_password(SERVICE_NAME, provider)

    # Check secure storage
    secure_key = keystore.get_key(provider)

    if keyring_key:
        if secure_key:
            print(f"  {provider}: Already in secure storage, removing from keyring...")
            try:
                keyring.delete_password(SERVICE_NAME, provider)
                print(f"    [OK] Removed from keyring")
            except Exception as e:
                print(f"    [!] Failed to remove from keyring: {e}")
        else:
            print(f"  {provider}: Migrating to secure storage...")
            keystore.set_key(provider, keyring_key)
            print(f"    [OK] Saved to encrypted storage")

            try:
                keyring.delete_password(SERVICE_NAME, provider)
                print(f"    [OK] Removed from keyring")
            except Exception as e:
                print(f"    [!] Failed to remove from keyring: {e}")

            migrated += 1
    elif secure_key:
        print(f"  {provider}: Already secure (not in keyring)")
        already_secure += 1
    else:
        print(f"  {provider}: No key found")

print("\n" + "=" * 50)
print(f"Migration complete!")
print(f"  Migrated: {migrated}")
print(f"  Already secure: {already_secure}")
print("=" * 50)

if migrated > 0 or already_secure > 0:
    print("\nYour API keys are now stored in encrypted local files:")
    print(f"  {keystore.keys_file}")
    print("\nAI agents can no longer access them via keyring.get_password()")
