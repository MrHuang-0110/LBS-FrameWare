from lbs_firmware_studio.backend.monitor_parser import MonitorParser


def test_single_complete_line():
    p = MonitorParser()
    frames = p.feed(b'{"a": 1}\r\n')
    assert frames == [{"a": 1}]


def test_multiple_lines_one_feed():
    p = MonitorParser()
    frames = p.feed(b'{"a": 1}\r\n{"b": 2}\r\n')
    assert frames == [{"a": 1}, {"b": 2}]


def test_half_line_across_chunks():
    p = MonitorParser()
    assert p.feed(b'{"a": ') == []          # 半行留缓冲
    assert p.feed(b'1}\r\n') == [{"a": 1}]   # 补齐后解析


def test_plain_newline_also_splits():
    p = MonitorParser()
    assert p.feed(b'{"a": 1}\n') == [{"a": 1}]


def test_bad_json_line_dropped_silently():
    p = MonitorParser()
    frames = p.feed(b'not json\r\n{"ok": 1}\r\n')
    assert frames == [{"ok": 1}]            # 坏行丢弃，好行保留


def test_non_object_json_dropped():
    p = MonitorParser()
    # 顶层非 dict（如数组/数字）丢弃，只保留 dict
    assert p.feed(b'[1,2]\r\n42\r\n{"x": 1}\r\n') == [{"x": 1}]


def test_buffer_overflow_resets():
    p = MonitorParser()
    p.feed(b"x" * (MonitorParser.MAX_BUFFER + 10))   # 无换行超上限 -> 清空
    assert p.feed(b'{"a": 1}\r\n') == [{"a": 1}]      # 清空后仍能正常解析


def test_feed_overlong_line_truncates():
    p = MonitorParser()
    # 单次喂入超长数据块、换行靠前：切行后残留的半行仍超限。
    # 旧守卫要求"完全无换行"才清空，此处带换行不触发，缓冲被撑破（T4-M1）。
    big = b"x" * (MonitorParser.MAX_BUFFER + 10)
    p.feed(b"\n" + big)
    assert len(p._buf) <= MonitorParser.MAX_BUFFER
    # 截断后缓冲仍可正常解析后续合法行
    assert p.feed(b'{"a": 1}\r\n') == [{"a": 1}]


def test_feed_overlong_across_chunks_truncates():
    p = MonitorParser()
    # 多次 feed 各自含换行、残留超长半行：旧守卫永不触发，缓冲持续膨胀。
    # 每次喂入后缓冲必须被上限守卫压回 MAX_BUFFER 以内。
    for _ in range(3):
        p.feed(b"\n" + b"y" * (MonitorParser.MAX_BUFFER + 10))
        assert len(p._buf) <= MonitorParser.MAX_BUFFER
