import json

import pytest


@pytest.fixture
def sample_diff() -> str:
    return """diff --git a/app.py b/app.py
index 1234567..89abcde 100644
--- a/app.py
+++ b/app.py
@@ -1,5 +1,12 @@
+import sqlite3
+
 def get_user(user_id):
-    return db.fetch(user_id)
+    query = f"SELECT * FROM users WHERE id = '{user_id}'"
+    return sqlite3.execute(query)
+
+def log_secret():
+    api_key = "sk-test-1234567890"
+    print(api_key)
"""


def build_signature(secret: str, payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    import hashlib
    import hmac

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, f"sha256={digest}"
