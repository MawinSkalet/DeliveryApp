import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pydantic import ValidationError

from app.errors import ApiError
from app.identity import current_customer_id, current_user_claims, current_user_id
from app.security import create_access_token, hash_password, verify_password
from app.users import (
    LoginInput,
    UserRegisterInput,
    _connection,
    get_user_by_id,
    login,
    register_user,
)


class TestSecurity(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AUTH_SECRET"] = os.getenv("AUTH_SECRET", "test-secret-key-1234567890-32bytes-secure")

    def test_password_hashing_and_verification(self) -> None:
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword123!", hashed))
        self.assertFalse(verify_password(password, "invalid_hash"))

    def test_create_access_token(self) -> None:
        user_id = uuid4()
        token = create_access_token(user_id=user_id, role="customer")
        claims = jwt.decode(
            token,
            os.environ["AUTH_SECRET"],
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        self.assertEqual(claims["sub"], str(user_id))
        self.assertEqual(claims["role"], "customer")
        self.assertGreater(claims["exp"], int(datetime.now(timezone.utc).timestamp()))


class TestValidation(unittest.TestCase):
    def test_register_input_valid(self) -> None:
        valid = UserRegisterInput(
            email="  User@Test.Com  ",
            name="  Test User  ",
            password="password123",
            role="customer",
        )
        self.assertEqual(valid.email, "User@Test.Com")
        self.assertEqual(valid.name, "Test User")

    def test_register_input_invalid_email(self) -> None:
        with self.assertRaises(ValidationError):
            UserRegisterInput(
                email="not-an-email",
                name="Test User",
                password="password123",
            )

    def test_register_input_empty_name(self) -> None:
        with self.assertRaises(ValidationError):
            UserRegisterInput(
                email="user@test.com",
                name="   ",
                password="password123",
            )

    def test_register_input_short_password(self) -> None:
        with self.assertRaises(ValidationError):
            UserRegisterInput(
                email="user@test.com",
                name="Test User",
                password="123",
            )


class TestIdentity(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AUTH_SECRET"] = os.getenv("AUTH_SECRET", "test-secret-key-1234567890-32bytes-secure")

    def test_current_user_claims_valid(self) -> None:
        user_id = uuid4()
        token = create_access_token(user_id=user_id, role="customer")
        claims = current_user_claims(f"Bearer {token}")
        self.assertEqual(claims["user_id"], user_id)
        self.assertEqual(claims["role"], "customer")

    def test_current_user_claims_missing_token(self) -> None:
        with self.assertRaises(ApiError) as ctx:
            current_user_claims("")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    def test_current_user_claims_invalid_token(self) -> None:
        with self.assertRaises(ApiError) as ctx:
            current_user_claims("Bearer invalid.token.payload")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.code, "UNAUTHENTICATED")

    def test_current_customer_id_role_check(self) -> None:
        user_id = uuid4()
        customer_token = create_access_token(user_id=user_id, role="customer")
        rider_token = create_access_token(user_id=user_id, role="rider")

        self.assertEqual(current_customer_id(f"Bearer {customer_token}"), user_id)

        with self.assertRaises(ApiError) as ctx:
            current_customer_id(f"Bearer {rider_token}")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.code, "FORBIDDEN")


class TestUsersDbIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            self.skipTest("DATABASE_URL not configured")
        os.environ["AUTH_SECRET"] = os.getenv("AUTH_SECRET", "test-secret-key-1234567890-32bytes-secure")

    def test_user_lifecycle_and_constraints(self) -> None:
        unique_suffix = uuid4().hex[:8]
        email_base = f"tester_{unique_suffix}@example.com"
        password = "SecurePassword123!"

        # 1. Register customer
        registered = register_user(
            UserRegisterInput(
                email=email_base,
                name="Integration Tester",
                password=password,
                role="customer",
            )
        )
        user_id = registered["id"]
        self.assertEqual(registered["email"], email_base)
        self.assertEqual(registered["role"], "customer")
        self.assertNotIn("password_hash", registered)

        try:
            # 2. Duplicate registration (exact match) -> 409
            with self.assertRaises(ApiError) as ctx:
                register_user(
                    UserRegisterInput(
                        email=email_base,
                        name="Duplicate Tester",
                        password=password,
                    )
                )
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(ctx.exception.code, "EMAIL_ALREADY_EXISTS")

            # 3. Duplicate registration (case-insensitive: UPPERCASE) -> 409
            with self.assertRaises(ApiError) as ctx_case:
                register_user(
                    UserRegisterInput(
                        email=email_base.upper(),
                        name="Uppercase Tester",
                        password=password,
                    )
                )
            self.assertEqual(ctx_case.exception.status_code, 409)
            self.assertEqual(ctx_case.exception.code, "EMAIL_ALREADY_EXISTS")

            # 4. Login with correct password and case-insensitive email
            login_result = login(
                LoginInput(
                    email=email_base.upper(),
                    password=password,
                )
            )
            token = login_result["access_token"]
            self.assertEqual(login_result["user"]["id"], user_id)

            # 5. Token is accepted by current_customer_id
            verified_id = current_customer_id(f"Bearer {token}")
            self.assertEqual(str(verified_id), user_id)

            # 6. Login with wrong password -> 401
            with self.assertRaises(ApiError) as ctx_pw:
                login(LoginInput(email=email_base, password="WrongPassword123!"))
            self.assertEqual(ctx_pw.exception.status_code, 401)
            self.assertEqual(ctx_pw.exception.code, "INVALID_CREDENTIALS")

            # 7. Authorized read own profile -> 200
            claims = current_user_claims(f"Bearer {token}")
            profile = get_user_by_id(user_id=uuid4() if False else verified_id, claims=claims)
            self.assertEqual(profile["id"], user_id)
            self.assertEqual(profile["email"], email_base)
            self.assertNotIn("password_hash", profile)

            # 8. Forbidden read (reading another user's profile) -> 403
            other_uuid = uuid4()
            with self.assertRaises(ApiError) as ctx_forbid:
                get_user_by_id(user_id=other_uuid, claims=claims)
            self.assertEqual(ctx_forbid.exception.status_code, 403)
            self.assertEqual(ctx_forbid.exception.code, "FORBIDDEN")

        finally:
            # Clean up test user
            with _connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestUsersHttpEndpoints(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["AUTH_SECRET"] = os.getenv("AUTH_SECRET", "test-secret-key-1234567890-32bytes-secure")
        from fastapi.testclient import TestClient
        from app.main import app

        self.client = TestClient(app)

    def test_health_check(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_register_validation_error_shape(self) -> None:
        response = self.client.post(
            "/api/v1/users",
            json={"email": "bad-email", "name": "", "password": "123"},
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("details", body["error"])

    def test_get_user_unauthenticated(self) -> None:
        response = self.client.get(f"/api/v1/users/{uuid4()}")
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"]["code"], "UNAUTHENTICATED")

    def test_get_user_invalid_token(self) -> None:
        response = self.client.get(
            f"/api/v1/users/{uuid4()}",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"]["code"], "UNAUTHENTICATED")

    def test_get_user_forbidden(self) -> None:
        user_a = uuid4()
        user_b = uuid4()
        token_a = create_access_token(user_id=user_a, role="customer")
        response = self.client.get(
            f"/api/v1/users/{user_b}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body["error"]["code"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()

