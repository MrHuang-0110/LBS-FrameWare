import textwrap
from lbs_firmware_studio.backend.profile import load_profiles


def test_load_three_products(tmp_path):
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            baud: 115200
            folders: [app, music, boot, config, version]
            firmware_dir: ./products/NEW-AI/fwlib
            script_dirs: {./products/NEW-AI/write: ./products/NEW-AI/app}
            chunk_size: 248
            last_frame_ack: wait_2s
            filename_encoding: gbk
            firmware_enter_cmd: RESET_FWLIB
            script_enter_cmd: RESET_FWLIB
            reopen_retries: 5
            reopen_delay: 2.0
          NEXT-AI:
            protocol: ymodem
            folders: [__single__]
            firmware_dir: ./products/NEXT-AI/fwlib
            script_dirs: {./products/NEXT-AI/write: ./products/NEXT-AI/app}
            chunk_size: 1024
            last_frame_ack: skip
            filename_encoding: utf-8
            firmware_enter_cmd: "ymodem update fmware\\r\\n"
            script_enter_cmd: "ymodem\\r\\n"
            reopen_retries: 40
            reopen_delay: 3.0
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    profiles = load_profiles(p)
    assert set(profiles) == {"NEW-AI", "NEXT-AI"}
    new = profiles["NEW-AI"]
    assert new.protocol == "custom_frame"
    assert new.folders == ["app", "music", "boot", "config", "version"]
    assert new.last_frame_ack == "wait_2s"
    assert new.firmware_enter_cmd == b"RESET_FWLIB"
    nxt = profiles["NEXT-AI"]
    assert nxt.protocol == "ymodem"
    assert nxt.script_enter_cmd == b"ymodem\r\n"
    assert nxt.firmware_enter_cmd == b"ymodem update fmware\r\n"


def test_max_slot_and_templates_dir(tmp_path):
    import textwrap as _tw
    from pathlib import Path
    yaml_text = _tw.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            max_slot: 19
          NEXT-AI:
            protocol: ymodem
            firmware_dir: ./products/NEXT-AI/fwlib
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].max_slot == 19
    assert profiles["NEXT-AI"].max_slot == 0   # 未配置默认 0
    # templates_dir 推导为 firmware_dir 的父目录下的 templates
    assert profiles["NEW-AI"].templates_dir == Path("./products/NEW-AI") / "templates"
