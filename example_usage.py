#!/usr/bin/env python3
"""
Example: How to use Secret Manager in your application

This demonstrates secure secret access without exposing sensitive values.
"""

import sys
sys.path.insert(0, 'src')

from secrets_manager import SecretManager


def example_1_basic_usage():
    """Example 1: Basic secret retrieval"""
    print("\n📖 Example 1: Basic Usage")
    print("-" * 50)

    manager = SecretManager()

    # Get a single secret (value never printed!)
    secret = manager.get_secret("my-api-key")

    if secret:
        print("✅ Secret retrieved successfully")
        print(f"   Length: {len(secret)} characters")
        # Use the secret in your application
        # api_client = APIClient(api_key=secret)
    else:
        print("❌ Secret not found or inaccessible")


def example_2_list_secrets():
    """Example 2: List available secrets"""
    print("\n📖 Example 2: List Available Secrets")
    print("-" * 50)

    manager = SecretManager()
    secrets = manager.list_secrets()

    print(f"Found {len(secrets)} secret(s):")
    for secret in secrets:
        accessible = "✅" if manager.verify_access(secret) else "❌"
        print(f"  {accessible} {secret}")


def example_3_load_to_environment():
    """Example 3: Load secrets into environment variables"""
    print("\n📖 Example 3: Load Secrets to Environment")
    print("-" * 50)

    manager = SecretManager()

    # Map environment variables to secret names
    secret_mapping = {
        "DATABASE_URL": "database-connection-string",
        "API_KEY": "external-api-key",
        "JWT_SECRET": "jwt-signing-key",
    }

    loaded = manager.load_secrets_to_env(secret_mapping)
    print(f"\n✅ Loaded {loaded} secret(s) into environment")

    # Now you can access them via os.environ
    # import os
    # db_url = os.environ.get("DATABASE_URL")


def example_4_safe_usage():
    """Example 4: Safe secret handling pattern"""
    print("\n📖 Example 4: Safe Secret Handling")
    print("-" * 50)

    manager = SecretManager()

    # Get secret
    api_key = manager.get_secret("api-key")

    if not api_key:
        print("❌ Cannot proceed without API key")
        return

    # Use secret in your application
    print("✅ Secret loaded - proceeding with application logic")

    # Example: Initialize API client
    # client = MyAPIClient(api_key=api_key)
    # response = client.do_something()

    # Clear sensitive data when done (optional)
    del api_key
    manager.clear_cache()
    print("🧹 Cleared sensitive data from memory")


def example_5_error_handling():
    """Example 5: Proper error handling"""
    print("\n📖 Example 5: Error Handling")
    print("-" * 50)

    manager = SecretManager()

    # Try to access a secret that might not exist
    secret = manager.get_secret("non-existent-secret")

    if secret is None:
        print("⚠️  Secret not found - using fallback behavior")
        # Implement fallback logic
        # use_default_config()
    else:
        print("✅ Secret found - using production config")
        # use_secret_config(secret)


def main():
    """Run all examples"""
    print("🔐 Secret Manager Usage Examples")
    print("=" * 50)

    examples = [
        example_1_basic_usage,
        example_2_list_secrets,
        example_3_load_to_environment,
        example_4_safe_usage,
        example_5_error_handling,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"❌ Example failed: {e}")

    print("\n✨ Examples complete!")
    print("\n💡 Best Practices:")
    print("   1. Never print or log secret values")
    print("   2. Use secrets only where needed")
    print("   3. Clear sensitive data when done")
    print("   4. Handle missing secrets gracefully")
    print("   5. Use environment variables for configuration")


if __name__ == "__main__":
    main()
