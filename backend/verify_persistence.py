import unittest
import os
import sqlite3
import database
import app as flask_app

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Use a test DB
        database.DB_FILE = "test_users.db"
        if os.path.exists("test_users.db"):
            os.remove("test_users.db")
        database.init_db()
        
        self.app = flask_app.app.test_client()

    def tearDown(self):
        if os.path.exists("test_users.db"):
            os.remove("test_users.db")

    def test_add_and_get_user(self):
        database.add_user("testuser", "🦁")
        users = database.get_all_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["username"], "testuser")
        self.assertEqual(users[0]["avatar"], "🦁")

    def test_api_endpoint(self):
        database.add_user("api_user", "🐼")
        response = self.app.get("/api/users")
        data = response.get_json()
        self.assertIn("users", data)
        self.assertEqual(len(data["users"]), 1)
        self.assertEqual(data["users"][0]["username"], "api_user")

    def test_duplicate_update(self):
        database.add_user("dup_user", "🦁")
        database.add_user("dup_user", "🦄") # Should update avatar
        users = database.get_all_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["avatar"], "🦄")

if __name__ == "__main__":
    unittest.main()
