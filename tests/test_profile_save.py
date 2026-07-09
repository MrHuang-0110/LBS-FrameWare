import textwrap
from pathlib import Path
from lbs_firmware_studio.backend.profile import load_profiles, save_profiles


def test_display_ports_loaded(tmp_path):
    p = tmp_path / "products.yaml"
    p.write_text(textwrap.dedent("""
        compiler_path: ./tools/rust-msc-latest-win10.exe
        products:
          NEW-AI:
            protocol: custom_frame
            display_ports: 8
    """))
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].display_ports == 8


def test_save_profiles_roundtrip(tmp_path):
    p = tmp_path / "products.yaml"
    raw = {
        "compiler_path": "./tools/x.exe",
        "products": {"NEW-AI": {"protocol": "custom_frame", "display_ports": 8}},
    }
    save_profiles(raw, p)
    # 读回应保留关键字段
    import yaml
    back = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert back["compiler_path"] == "./tools/x.exe"
    assert back["products"]["NEW-AI"]["protocol"] == "custom_frame"
    # load_profiles 也能正常解析
    profiles = load_profiles(p)
    assert profiles["NEW-AI"].protocol == "custom_frame"
