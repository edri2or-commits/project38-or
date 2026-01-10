"""Tests for the GitHub App authentication module.

Note: These tests use mocking to avoid actual API calls.
Tokens are NEVER printed or exposed in test output.
"""

from unittest.mock import MagicMock, patch

from src.github_auth import (
    GITHUB_APP_ID,
    GITHUB_INSTALLATION_ID,
    configure_gh_cli,
    generate_jwt,
    get_installation_token,
)


class TestGenerateJWT:
    """Tests for JWT generation."""

    def test_generate_jwt_returns_string(self):
        """Test that generate_jwt returns a non-empty string."""
        # Use a test private key (this is a dummy key for testing only)
        test_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MAs9MNWLxIgXbs7p
5hB4TaAg6leKeg9HxuGdSQh6rLdOOwEr+xMMpC3MEqmjkX2u3lXgSBon4VL3aAPK
EQUxfcyKF2FBjqSKuH+36oIHqXTKrY7hZFzGSKxSIkENPTbeJtEDzBEp8SGCy+4t
FW85z7wUacoU8JpQXxINBLUQFLK0QYaUw+OiNVwTJ8yGXONLbO0XQDU5ELE7A3CX
xOvZg5PsM4Rjqq3Z1yK2nPKj2P0VgA+Lr/Nw8pYQSJYCjuvEcM0NXhqd3dX4FMQO
eDCKgfB0gCK9MghbVngYXJCbJcjfHdKrjqVJ3wIDAQABAoIBAC1aw2lZPzqMI4N3
FT6slLTcPOHhFn0ZD6cLTc0fZ+F36Aw4pNGG8PQhE4OCSTiMNLLm+yXN0Gt2TMAE
8cqH7YL33w5Y3wxYCQBHyoFLw8AaeCqvFgdL5vA3zFpGzaGJwMy0Z0sBfmGDr0Dx
E5fK0x0da4YJKuvkF1KnMzF4qB0y3E7QUaHw3CjFVqsw1MJ+0QXZJxLbGrM3Jhx5
UH6qPgTJSoOI2V4O1rUreSQN9J7cW4h/aGbxBKLkb6Rr4qFeJFKPJ3JkZpnNqF2q
1m3M7xSFq6McJkQxA9EBk8SZQKDj5PkS3xv/82VNrHwL5+bJKOv3XSoDsHwz+5sZ
6uXSa8ECgYEA6VoLJT3q3cKiE8mYLU5wDmfL0AZyKyoN3dKb5I0nbLONJxdWJ2r8
h5KPIL4Bax0WOCYgDNFL1PRLwJVU8WAF1DPxRTNXqP6h6jWrm+YMl8xOqPvFpKB0
J2hBwUYoSQV0Lr3C7gZwBAmCBQHRIxNqZJyWZPqXmQBK5QXSKXFL3d8CgYEA5dF2
nkxBJZcKPNqDg8wFeDsHYUfDfP/37rLzYc+PfJmI0mmFK8QLRUisj8c+BPjMf5eZ
QjWpnTaHCv6Ss8rG2uANjfn0Ml/WL5ckP0ZP5eSLcx4+wnqk0LAoKy5R5t9ZjHqW
VhX5n6FVMHPLXP2W5L4+yqp3S0vR7zJzLn8yE7ECgYBU7N7fE2DFBopPgqJF45v4
JEIk9j3vMqZ5l4cRpSJMh/bTpNH0UM6zdMH/2Kyiexq3L8Y2uHkify4RxAoV7Tz5
APoGSvNzOZaLbJ1H6bKi7V5cMUP6q0TWsl7IuM7lpqv8xO9w0jP+QmpO0BPBHKVN
7V5c8vJwh+BcUm+BBcVdhwKBgQCvw5O8rJq4bI7QHr4YdNTM+f9oJD/9aNP5UJfY
cOE5K4HVE0FiG6UE0rRLm5KPjZpJqpBh4xfeSOn1POzLuX0AEf8MSLSX5R7xC7vS
P5p+aM3gHfqYbrkx9D2qKbK7d03+TpvLhS3Y3myJOM4CR30L7+JT+A+cD0d1r/UT
3LshcQKBgQCbH8WVaFp1FBnqCgIeU2kFw0lQOcOWJtbB7LMrf0P6d4yP0xoL+Qap
/3SvxC6qXbsMP8rWLm+N7Y9B/AOP0GJ6T+pdH3fi03Q5m5tOSdNzshwl9oalH5F/
E5Nd2l9ksLJ9vVi6cP0CF5UA9kNo1kMoRW30hDT0BRDrqu3yUA==
-----END RSA PRIVATE KEY-----"""

        result = generate_jwt(GITHUB_APP_ID, test_key)

        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # JWT has 3 parts separated by dots
        assert result.count(".") == 2

    def test_generate_jwt_structure(self):
        """Test that JWT has correct structure."""
        test_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MAs9MNWLxIgXbs7p
5hB4TaAg6leKeg9HxuGdSQh6rLdOOwEr+xMMpC3MEqmjkX2u3lXgSBon4VL3aAPK
EQUxfcyKF2FBjqSKuH+36oIHqXTKrY7hZFzGSKxSIkENPTbeJtEDzBEp8SGCy+4t
FW85z7wUacoU8JpQXxINBLUQFLK0QYaUw+OiNVwTJ8yGXONLbO0XQDU5ELE7A3CX
xOvZg5PsM4Rjqq3Z1yK2nPKj2P0VgA+Lr/Nw8pYQSJYCjuvEcM0NXhqd3dX4FMQO
eDCKgfB0gCK9MghbVngYXJCbJcjfHdKrjqVJ3wIDAQABAoIBAC1aw2lZPzqMI4N3
FT6slLTcPOHhFn0ZD6cLTc0fZ+F36Aw4pNGG8PQhE4OCSTiMNLLm+yXN0Gt2TMAE
8cqH7YL33w5Y3wxYCQBHyoFLw8AaeCqvFgdL5vA3zFpGzaGJwMy0Z0sBfmGDr0Dx
E5fK0x0da4YJKuvkF1KnMzF4qB0y3E7QUaHw3CjFVqsw1MJ+0QXZJxLbGrM3Jhx5
UH6qPgTJSoOI2V4O1rUreSQN9J7cW4h/aGbxBKLkb6Rr4qFeJFKPJ3JkZpnNqF2q
1m3M7xSFq6McJkQxA9EBk8SZQKDj5PkS3xv/82VNrHwL5+bJKOv3XSoDsHwz+5sZ
6uXSa8ECgYEA6VoLJT3q3cKiE8mYLU5wDmfL0AZyKyoN3dKb5I0nbLONJxdWJ2r8
h5KPIL4Bax0WOCYgDNFL1PRLwJVU8WAF1DPxRTNXqP6h6jWrm+YMl8xOqPvFpKB0
J2hBwUYoSQV0Lr3C7gZwBAmCBQHRIxNqZJyWZPqXmQBK5QXSKXFL3d8CgYEA5dF2
nkxBJZcKPNqDg8wFeDsHYUfDfP/37rLzYc+PfJmI0mmFK8QLRUisj8c+BPjMf5eZ
QjWpnTaHCv6Ss8rG2uANjfn0Ml/WL5ckP0ZP5eSLcx4+wnqk0LAoKy5R5t9ZjHqW
VhX5n6FVMHPLXP2W5L4+yqp3S0vR7zJzLn8yE7ECgYBU7N7fE2DFBopPgqJF45v4
JEIk9j3vMqZ5l4cRpSJMh/bTpNH0UM6zdMH/2Kyiexq3L8Y2uHkify4RxAoV7Tz5
APoGSvNzOZaLbJ1H6bKi7V5cMUP6q0TWsl7IuM7lpqv8xO9w0jP+QmpO0BPBHKVN
7V5c8vJwh+BcUm+BBcVdhwKBgQCvw5O8rJq4bI7QHr4YdNTM+f9oJD/9aNP5UJfY
cOE5K4HVE0FiG6UE0rRLm5KPjZpJqpBh4xfeSOn1POzLuX0AEf8MSLSX5R7xC7vS
P5p+aM3gHfqYbrkx9D2qKbK7d03+TpvLhS3Y3myJOM4CR30L7+JT+A+cD0d1r/UT
3LshcQKBgQCbH8WVaFp1FBnqCgIeU2kFw0lQOcOWJtbB7LMrf0P6d4yP0xoL+Qap
/3SvxC6qXbsMP8rWLm+N7Y9B/AOP0GJ6T+pdH3fi03Q5m5tOSdNzshwl9oalH5F/
E5Nd2l9ksLJ9vVi6cP0CF5UA9kNo1kMoRW30hDT0BRDrqu3yUA==
-----END RSA PRIVATE KEY-----"""

        result = generate_jwt(12345, test_key)
        parts = result.split(".")

        assert len(parts) == 3
        # Header and payload should be base64url encoded
        assert all(len(part) > 0 for part in parts)


class TestGetInstallationToken:
    """Tests for installation token retrieval."""

    def test_get_installation_token_success(self):
        """Test successful token retrieval."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            with patch("src.github_auth.requests.post") as mock_post:
                # Setup mock secret manager
                mock_sm.return_value.get_secret.return_value = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MAs9MNWLxIgXbs7p
5hB4TaAg6leKeg9HxuGdSQh6rLdOOwEr+xMMpC3MEqmjkX2u3lXgSBon4VL3aAPK
EQUxfcyKF2FBjqSKuH+36oIHqXTKrY7hZFzGSKxSIkENPTbeJtEDzBEp8SGCy+4t
FW85z7wUacoU8JpQXxINBLUQFLK0QYaUw+OiNVwTJ8yGXONLbO0XQDU5ELE7A3CX
xOvZg5PsM4Rjqq3Z1yK2nPKj2P0VgA+Lr/Nw8pYQSJYCjuvEcM0NXhqd3dX4FMQO
eDCKgfB0gCK9MghbVngYXJCbJcjfHdKrjqVJ3wIDAQABAoIBAC1aw2lZPzqMI4N3
FT6slLTcPOHhFn0ZD6cLTc0fZ+F36Aw4pNGG8PQhE4OCSTiMNLLm+yXN0Gt2TMAE
8cqH7YL33w5Y3wxYCQBHyoFLw8AaeCqvFgdL5vA3zFpGzaGJwMy0Z0sBfmGDr0Dx
E5fK0x0da4YJKuvkF1KnMzF4qB0y3E7QUaHw3CjFVqsw1MJ+0QXZJxLbGrM3Jhx5
UH6qPgTJSoOI2V4O1rUreSQN9J7cW4h/aGbxBKLkb6Rr4qFeJFKPJ3JkZpnNqF2q
1m3M7xSFq6McJkQxA9EBk8SZQKDj5PkS3xv/82VNrHwL5+bJKOv3XSoDsHwz+5sZ
6uXSa8ECgYEA6VoLJT3q3cKiE8mYLU5wDmfL0AZyKyoN3dKb5I0nbLONJxdWJ2r8
h5KPIL4Bax0WOCYgDNFL1PRLwJVU8WAF1DPxRTNXqP6h6jWrm+YMl8xOqPvFpKB0
J2hBwUYoSQV0Lr3C7gZwBAmCBQHRIxNqZJyWZPqXmQBK5QXSKXFL3d8CgYEA5dF2
nkxBJZcKPNqDg8wFeDsHYUfDfP/37rLzYc+PfJmI0mmFK8QLRUisj8c+BPjMf5eZ
QjWpnTaHCv6Ss8rG2uANjfn0Ml/WL5ckP0ZP5eSLcx4+wnqk0LAoKy5R5t9ZjHqW
VhX5n6FVMHPLXP2W5L4+yqp3S0vR7zJzLn8yE7ECgYBU7N7fE2DFBopPgqJF45v4
JEIk9j3vMqZ5l4cRpSJMh/bTpNH0UM6zdMH/2Kyiexq3L8Y2uHkify4RxAoV7Tz5
APoGSvNzOZaLbJ1H6bKi7V5cMUP6q0TWsl7IuM7lpqv8xO9w0jP+QmpO0BPBHKVN
7V5c8vJwh+BcUm+BBcVdhwKBgQCvw5O8rJq4bI7QHr4YdNTM+f9oJD/9aNP5UJfY
cOE5K4HVE0FiG6UE0rRLm5KPjZpJqpBh4xfeSOn1POzLuX0AEf8MSLSX5R7xC7vS
P5p+aM3gHfqYbrkx9D2qKbK7d03+TpvLhS3Y3myJOM4CR30L7+JT+A+cD0d1r/UT
3LshcQKBgQCbH8WVaFp1FBnqCgIeU2kFw0lQOcOWJtbB7LMrf0P6d4yP0xoL+Qap
/3SvxC6qXbsMP8rWLm+N7Y9B/AOP0GJ6T+pdH3fi03Q5m5tOSdNzshwl9oalH5F/
E5Nd2l9ksLJ9vVi6cP0CF5UA9kNo1kMoRW30hDT0BRDrqu3yUA==
-----END RSA PRIVATE KEY-----"""

                # Setup mock API response
                mock_response = MagicMock()
                mock_response.json.return_value = {"token": "ghs_test_token_123"}
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response

                result = get_installation_token()

                # Token should be returned (but never printed!)
                assert result is not None
                assert len(result) > 0

    def test_get_installation_token_no_private_key(self):
        """Test behavior when private key is not available."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            mock_sm.return_value.get_secret.return_value = None

            result = get_installation_token()

            assert result is None

    def test_get_installation_token_api_error(self):
        """Test behavior when GitHub API returns an error."""
        with patch("src.github_auth.SecretManager") as mock_sm:
            with patch("src.github_auth.requests.post") as mock_post:
                import requests

                mock_sm.return_value.get_secret.return_value = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MAs9MNWLxIgXbs7p
5hB4TaAg6leKeg9HxuGdSQh6rLdOOwEr+xMMpC3MEqmjkX2u3lXgSBon4VL3aAPK
EQUxfcyKF2FBjqSKuH+36oIHqXTKrY7hZFzGSKxSIkENPTbeJtEDzBEp8SGCy+4t
FW85z7wUacoU8JpQXxINBLUQFLK0QYaUw+OiNVwTJ8yGXONLbO0XQDU5ELE7A3CX
xOvZg5PsM4Rjqq3Z1yK2nPKj2P0VgA+Lr/Nw8pYQSJYCjuvEcM0NXhqd3dX4FMQO
eDCKgfB0gCK9MghbVngYXJCbJcjfHdKrjqVJ3wIDAQABAoIBAC1aw2lZPzqMI4N3
FT6slLTcPOHhFn0ZD6cLTc0fZ+F36Aw4pNGG8PQhE4OCSTiMNLLm+yXN0Gt2TMAE
8cqH7YL33w5Y3wxYCQBHyoFLw8AaeCqvFgdL5vA3zFpGzaGJwMy0Z0sBfmGDr0Dx
E5fK0x0da4YJKuvkF1KnMzF4qB0y3E7QUaHw3CjFVqsw1MJ+0QXZJxLbGrM3Jhx5
UH6qPgTJSoOI2V4O1rUreSQN9J7cW4h/aGbxBKLkb6Rr4qFeJFKPJ3JkZpnNqF2q
1m3M7xSFq6McJkQxA9EBk8SZQKDj5PkS3xv/82VNrHwL5+bJKOv3XSoDsHwz+5sZ
6uXSa8ECgYEA6VoLJT3q3cKiE8mYLU5wDmfL0AZyKyoN3dKb5I0nbLONJxdWJ2r8
h5KPIL4Bax0WOCYgDNFL1PRLwJVU8WAF1DPxRTNXqP6h6jWrm+YMl8xOqPvFpKB0
J2hBwUYoSQV0Lr3C7gZwBAmCBQHRIxNqZJyWZPqXmQBK5QXSKXFL3d8CgYEA5dF2
nkxBJZcKPNqDg8wFeDsHYUfDfP/37rLzYc+PfJmI0mmFK8QLRUisj8c+BPjMf5eZ
QjWpnTaHCv6Ss8rG2uANjfn0Ml/WL5ckP0ZP5eSLcx4+wnqk0LAoKy5R5t9ZjHqW
VhX5n6FVMHPLXP2W5L4+yqp3S0vR7zJzLn8yE7ECgYBU7N7fE2DFBopPgqJF45v4
JEIk9j3vMqZ5l4cRpSJMh/bTpNH0UM6zdMH/2Kyiexq3L8Y2uHkify4RxAoV7Tz5
APoGSvNzOZaLbJ1H6bKi7V5cMUP6q0TWsl7IuM7lpqv8xO9w0jP+QmpO0BPBHKVN
7V5c8vJwh+BcUm+BBcVdhwKBgQCvw5O8rJq4bI7QHr4YdNTM+f9oJD/9aNP5UJfY
cOE5K4HVE0FiG6UE0rRLm5KPjZpJqpBh4xfeSOn1POzLuX0AEf8MSLSX5R7xC7vS
P5p+aM3gHfqYbrkx9D2qKbK7d03+TpvLhS3Y3myJOM4CR30L7+JT+A+cD0d1r/UT
3LshcQKBgQCbH8WVaFp1FBnqCgIeU2kFw0lQOcOWJtbB7LMrf0P6d4yP0xoL+Qap
/3SvxC6qXbsMP8rWLm+N7Y9B/AOP0GJ6T+pdH3fi03Q5m5tOSdNzshwl9oalH5F/
E5Nd2l9ksLJ9vVi6cP0CF5UA9kNo1kMoRW30hDT0BRDrqu3yUA==
-----END RSA PRIVATE KEY-----"""
                mock_post.side_effect = requests.RequestException("API error")

                result = get_installation_token()

                assert result is None


class TestConfigureGhCli:
    """Tests for gh CLI configuration."""

    def test_configure_gh_cli_no_token(self):
        """Test behavior when token cannot be obtained."""
        with patch("src.github_auth.get_installation_token") as mock_get_token:
            mock_get_token.return_value = None

            result = configure_gh_cli()

            assert result is False

    def test_configure_gh_cli_no_gh_executable(self):
        """Test behavior when gh is not installed."""
        with patch("src.github_auth.get_installation_token") as mock_get_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                mock_get_token.return_value = "test_token"
                mock_which.return_value = None

                result = configure_gh_cli()

                assert result is False

    def test_configure_gh_cli_success(self):
        """Test successful gh CLI configuration."""
        with patch("src.github_auth.get_installation_token") as mock_get_token:
            with patch("src.github_auth.shutil.which") as mock_which:
                with patch("src.github_auth.subprocess.run") as mock_run:
                    mock_get_token.return_value = "test_token"
                    mock_which.return_value = "/usr/bin/gh"
                    mock_run.return_value = MagicMock(returncode=0)

                    result = configure_gh_cli()

                    assert result is True


class TestConstants:
    """Tests for module constants."""

    def test_app_id_is_set(self):
        """Test that App ID is configured."""
        assert GITHUB_APP_ID == 2497877

    def test_installation_id_is_set(self):
        """Test that Installation ID is configured."""
        assert GITHUB_INSTALLATION_ID == 100231961
