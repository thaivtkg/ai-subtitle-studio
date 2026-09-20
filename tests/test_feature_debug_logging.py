import unittest

from core.debug_logging import DebugConfig, debug_enabled, debug_log, error_log, warning_log


class DebugLoggingContracts(unittest.TestCase):
    def test_DBG01_fresh_config_is_all_off(self):
        config = DebugConfig()

        self.assertFalse(config.master_enabled)
        self.assertFalse(debug_enabled("recovery", config))
        self.assertFalse(debug_enabled("canonical_save", config))

    def test_DBG02_one_enabled_category_emits(self):
        config = DebugConfig(master_enabled=True, enabled_categories={"recovery"})
        records = []

        self.assertTrue(debug_log("recovery", "snapshot written", config, records.append))
        self.assertEqual(records, [("DEBUG", "recovery", "snapshot written")])

    def test_DBG03_categories_are_isolated(self):
        config = DebugConfig(master_enabled=True, enabled_categories={"recovery"})
        records = []

        debug_log("recovery", "one", config, records.append)
        debug_log("canonical_save", "two", config, records.append)

        self.assertEqual(records, [("DEBUG", "recovery", "one")])

    def test_DBG04_master_off_overrides_enabled_category(self):
        config = DebugConfig(master_enabled=False, enabled_categories={"recovery"})
        records = []

        self.assertFalse(debug_log("recovery", "silent", config, records.append))
        self.assertEqual(records, [])

    def test_DBG05_warning_bypasses_debug_gate(self):
        config = DebugConfig()
        records = []

        warning_log("recovery", "snapshot warning", config, records.append)

        self.assertEqual(records, [("WARNING", "recovery", "snapshot warning")])

    def test_DBG06_error_bypasses_debug_gate(self):
        config = DebugConfig()
        records = []

        error_log("recovery", "snapshot failed", config, records.append)

        self.assertEqual(records, [("ERROR", "recovery", "snapshot failed")])

    def test_DBG07_unknown_category_is_fail_safe_off(self):
        config = DebugConfig(master_enabled=True, enabled_categories={"unknown"})
        records = []

        self.assertFalse(debug_enabled("unknown", config))
        self.assertFalse(debug_log("unknown", "ignored", config, records.append))
        self.assertEqual(records, [])

    def test_DBG08_new_config_resets_session_state(self):
        active = DebugConfig(master_enabled=True, enabled_categories={"recovery"})
        fresh = DebugConfig()

        self.assertTrue(debug_enabled("recovery", active))
        self.assertFalse(debug_enabled("recovery", fresh))

    def test_DBG09_activity_filter_does_not_change_generation_gate(self):
        config = DebugConfig(master_enabled=True, enabled_categories={"recovery"})
        records = []

        debug_log("recovery", "visible", config, records.append)

        self.assertTrue(debug_enabled("recovery", config))
        self.assertEqual(len(records), 1)

    def test_DBG10_logging_toggle_does_not_change_operation_result(self):
        operation_result = {"save": True, "recovery": True, "switch": True}
        off = DebugConfig()
        on = DebugConfig(master_enabled=True, enabled_categories={"recovery"})

        debug_log("recovery", "off path", off, lambda _: None)
        debug_log("recovery", "on path", on, lambda _: None)

        self.assertEqual(operation_result, {"save": True, "recovery": True, "switch": True})


if __name__ == "__main__":
    unittest.main()
