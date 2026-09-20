# Auth integration tests

These tests run only when `TEST_DATABASE_URL` points to a dedicated MySQL test database. Create and migrate that database manually; do not point this variable at a development, staging, or production database.

Example command after manually applying Alembic to `nestora_auth_test`:

```bash
TEST_DATABASE_URL='mysql+aiomysql://test_user:test_password@127.0.0.1:3306/nestora_auth_test' pytest -m integration
```

The tests create and remove only uniquely named test rows. They verify that a committed logout revokes a stored opaque session and that an expired session cannot authenticate.
