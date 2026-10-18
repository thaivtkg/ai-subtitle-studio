from core.subtitle_controller import SubtitleController


def test_update_live_data_supports_dict_segments_without_key_error():
    controller = SubtitleController()
    changes = []
    controller.subtitle_changed.connect(lambda *args: changes.append(args))

    controller.update_live_data([
        {"start_ms": 1000, "end_ms": 2000, "text": "first", "stt": 1},
        {"start": "00:00:02,000", "end": "00:00:03,000", "text": "second", "stt": 2},
    ])
    controller.sync_position(2500)

    assert changes == [(2, 2000, "second")]


def test_update_live_data_supports_tuple_segments():
    controller = SubtitleController()
    changes = []
    controller.subtitle_changed.connect(lambda *args: changes.append(args))

    controller.update_live_data([
        (1000, 2000, "first", 1),
        (2000, 3000, "second", 2),
    ])
    controller.sync_position(1500)

    assert changes == [(1, 1000, "first")]
