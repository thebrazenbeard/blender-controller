import unittest
from blender_controller.policy import ViewGrants


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.clock = [100.0]
        self.grants = ViewGrants(now=lambda: self.clock[0])

    def test_attended_grant_is_scoped_to_window_and_process(self):
        grant = self.grants.issue(1234, 55)
        self.grants.check(grant.token, 1234, 55)
        for args in [(grant.token, 1235, 55), (grant.token, 1234, 56),
                     ("wrong-token", 1234, 55)]:
            with self.assertRaises(PermissionError):
                self.grants.check(*args)

    def test_grant_expires_and_cannot_be_replayed(self):
        grant = self.grants.issue(1234, 55)
        self.clock[0] += 120
        with self.assertRaises(PermissionError):
            self.grants.check(grant.token, 1234, 55)

    def test_rate_limiter(self):
        grant = self.grants.issue(1234, 55)
        self.grants.check(grant.token, 1234, 55, capture=True)
        with self.assertRaises(PermissionError):
            self.grants.check(grant.token, 1234, 55, capture=True)
        self.clock[0] += 0.5
        self.grants.check(grant.token, 1234, 55, capture=True)

    def test_revocation_and_reissue(self):
        first = self.grants.issue(1234, 55)
        second = self.grants.issue(1234, 55)
        with self.assertRaises(PermissionError):
            self.grants.check(first.token, 1234, 55)
        with self.assertRaises(PermissionError):
            self.grants.revoke(first.token)
        self.grants.revoke(second.token)
        with self.assertRaises(PermissionError):
            self.grants.check(second.token, 1234, 55)

    def test_invalid_targets_fail(self):
        for hwnd, pid in [(0, 10), (10, 0), (-1, 3), ("123", 3)]:
            with self.assertRaises(ValueError):
                self.grants.issue(hwnd, pid)


if __name__ == "__main__":
    unittest.main()
