import unittest

from core.app_context import build_startup_context


class TestC2ContextDerivation(unittest.TestCase):

    def test_clean_primary_launch_yields_default_context(self):
        """Clean primary launch -> StartupContext(recovery=False, external_open=False)"""
        args = ["main.py"]
        context = build_startup_context(sys_args=args, has_pending_recovery=False)

        self.assertFalse(context.recovery)
        self.assertFalse(context.external_open)

    def test_primary_launch_with_external_path_yields_external_open(self):
        """Primary launch with external path -> StartupContext(recovery=False, external_open=True)"""
        args = ["main.py", "C:/videos/test_media.mp4"]
        context = build_startup_context(sys_args=args, has_pending_recovery=False)

        self.assertFalse(context.recovery)
        self.assertTrue(context.external_open, "Must detect external open via sys_args")

    def test_recovery_accepted_yields_recovery_context(self):
        """Recovery accepted/active -> StartupContext(recovery=True, external_open=False)"""
        args = ["main.py"]
        context = build_startup_context(sys_args=args, has_pending_recovery=True)

        self.assertTrue(context.recovery, "Must detect recovery")
        self.assertFalse(context.external_open)

    def test_recovery_with_external_path_yields_combined_context(self):
        """Recovery + external path -> StartupContext(recovery=True, external_open=True)"""
        args = ["main.py", "C:/videos/test_media.mp4"]
        context = build_startup_context(sys_args=args, has_pending_recovery=True)

        self.assertTrue(context.recovery)
        self.assertTrue(context.external_open)


if __name__ == "__main__":
    unittest.main()
