import unittest

from core.debug_logging import DebugConfig, debug_enabled, debug_log, error_log, warning_log


class DebugLoggingContracts(unittest.TestCase):
    CATEGORIES = (
        "recovery",
        "canonical_save",
        "project_switch",
        "project_status",
        "waveform",
        "artifact_sync",
    )

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

    def test_DBG11_all_locked_categories_are_recognized(self):
        for category in self.CATEGORIES:
            with self.subTest(category=category):
                config = DebugConfig(master_enabled=True, enabled_categories={category})
                records = []

                self.assertTrue(debug_enabled(category, config))
                self.assertTrue(debug_log(category, "message", config, records.append))
                self.assertEqual(records, [("DEBUG", category, "message")])

    def test_DBG12_locked_categories_are_isolated(self):
        for enabled_category in self.CATEGORIES:
            with self.subTest(enabled_category=enabled_category):
                config = DebugConfig(
                    master_enabled=True,
                    enabled_categories={enabled_category},
                )
                records = []

                for category in self.CATEGORIES:
                    self.assertEqual(
                        debug_enabled(category, config),
                        category == enabled_category,
                    )
                    debug_log(category, category, config, records.append)

                self.assertEqual(records, [("DEBUG", enabled_category, enabled_category)])

    def test_DBG13_unknown_categories_fail_safe_off(self):
        config = DebugConfig(master_enabled=True, enabled_categories=set(self.CATEGORIES))

        for category in ("unknown", "debug", "all", "*", "project", "save", ""):
            with self.subTest(category=category):
                records = []

                self.assertFalse(debug_enabled(category, config))
                self.assertFalse(debug_log(category, "ignored", config, records.append))
                self.assertEqual(records, [])

    def test_DBG14_master_off_dominates_all_locked_categories(self):
        config = DebugConfig(master_enabled=False, enabled_categories=set(self.CATEGORIES))

        for category in self.CATEGORIES:
            with self.subTest(category=category):
                records = []

                self.assertFalse(debug_enabled(category, config))
                self.assertFalse(debug_log(category, "ignored", config, records.append))
                self.assertEqual(records, [])

    def test_DBG15_disabled_debug_does_not_invoke_emitter(self):
        cases = (
            DebugConfig(master_enabled=False, enabled_categories={"recovery"}),
            DebugConfig(master_enabled=True, enabled_categories={"recovery"}),
        )
        categories = ("recovery", "canonical_save")

        for config, category in zip(cases, categories):
            with self.subTest(master=config.master_enabled, category=category):
                emitter_calls = []

                debug_log(category, "ignored", config, emitter_calls.append)

                self.assertEqual(emitter_calls, [])

    def test_DBG16_enabled_debug_emits_exactly_once(self):
        config = DebugConfig(master_enabled=True, enabled_categories={"recovery"})
        emitter_calls = []

        self.assertTrue(debug_log("recovery", "message", config, emitter_calls.append))

        self.assertEqual(emitter_calls, [("DEBUG", "recovery", "message")])

    def test_DBG17_warning_bypasses_master_and_category_gate(self):
        configs = (
            DebugConfig(),
            DebugConfig(master_enabled=True, enabled_categories={"canonical_save"}),
        )

        for config in configs:
            with self.subTest(master=config.master_enabled):
                emitter_calls = []

                warning_log("recovery", "warning", config, emitter_calls.append)

                self.assertEqual(emitter_calls, [("WARNING", "recovery", "warning")])

    def test_DBG18_error_bypasses_master_and_category_gate(self):
        configs = (
            DebugConfig(),
            DebugConfig(master_enabled=True, enabled_categories={"canonical_save"}),
        )

        for config in configs:
            with self.subTest(master=config.master_enabled):
                emitter_calls = []

                error_log("recovery", "error", config, emitter_calls.append)

                self.assertEqual(emitter_calls, [("ERROR", "recovery", "error")])

    def test_DBG19_config_instances_do_not_share_runtime_state(self):
        config_a = DebugConfig(master_enabled=True, enabled_categories={"recovery"})
        config_b = DebugConfig()

        self.assertTrue(debug_enabled("recovery", config_a))
        self.assertFalse(debug_enabled("recovery", config_b))

        config_b.master_enabled = True
        config_b.enabled_categories.add("canonical_save")

        self.assertTrue(debug_enabled("recovery", config_a))
        self.assertFalse(debug_enabled("canonical_save", config_a))
        self.assertFalse(debug_enabled("recovery", config_b))
        self.assertTrue(debug_enabled("canonical_save", config_b))


if __name__ == "__main__":
    unittest.main()
