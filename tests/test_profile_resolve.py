import textwrap
from pathlib import Path
from lbs_firmware_studio.backend.profile import load_profiles


def _write(tmp_path):
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/comp.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            script_dirs: {./products/NEW-AI/write: ./products/NEW-AI/app}
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    return p


def test_firmware_dir_resolved_absolute(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.firmware_dir.is_absolute()
    assert prof.firmware_dir == (tmp_path / "products/NEW-AI/fwlib").resolve()


def test_compiler_path_resolved_absolute(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.compiler_path == (tmp_path / "tools/comp.exe").resolve()


def test_script_dirs_key_and_value_resolved(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    items = list(prof.script_dirs.items())
    assert items[0][0] == (tmp_path / "products/NEW-AI/write").resolve()
    assert items[0][1] == (tmp_path / "products/NEW-AI/app").resolve()


def test_templates_dir_resolved_absolute(tmp_path):
    p = _write(tmp_path)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.templates_dir == (tmp_path / "products/NEW-AI/templates").resolve()


def test_explicit_templates_dir_used(tmp_path):
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/comp.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            templates_dir: ./products/NEW-AI/templates
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.templates_dir == (tmp_path / "products/NEW-AI/templates").resolve()


def test_explicit_templates_dir_independent_of_firmware(tmp_path):
    # firmware_dir is absolute and elsewhere; templates_dir must NOT be derived from it
    abs_fw = (tmp_path / "ext" / "fw").resolve().as_posix()
    yaml_text = f"""
compiler_path: ./tools/comp.exe
products:
  NEW-AI:
    protocol: custom_frame
    firmware_dir: {abs_fw}
    templates_dir: ./products/NEW-AI/templates
"""
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.templates_dir == (tmp_path / "products/NEW-AI/templates").resolve()
    # And definitely NOT under the absolute firmware dir parent
    assert (tmp_path / "ext").resolve() not in prof.templates_dir.parents


def test_templates_dir_falls_back_when_absent(tmp_path):
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/comp.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.templates_dir == (tmp_path / "products/NEW-AI/templates").resolve()


def test_absolute_input_preserved(tmp_path):
    abs_fw = (tmp_path / "elsewhere" / "fw").resolve()
    yaml_text = f"""
compiler_path: ./tools/comp.exe
products:
  NEW-AI:
    protocol: custom_frame
    firmware_dir: {abs_fw.as_posix()}
"""
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.firmware_dir == abs_fw   # 绝对路径原样


def test_roundtrip_backslash_value_no_mis_escape(tmp_path):
    """T4-PR1：含反斜杠值（如 Windows 路径）不能被 _to_bytes 的 unicode_escape 误转义。"""
    from lbs_firmware_studio.backend.profile import _to_bytes
    # \f 是 unicode_escape 转义（form feed），必须按字面保留
    assert _to_bytes(r"C:\fw\lib") == b"C:\\fw\\lib"
    # \U 后跟非 8 位十六进制在 Python 3.12+ 抛 UnicodeDecodeError，不得崩溃
    assert _to_bytes(r"C:\Users\dev") == b"C:\\Users\\dev"
    # 受控转义 \r\n 仍按字面解释（既有语义：YAML 单引号 "ymodem\r\n" -> b"ymodem\r\n"）
    assert _to_bytes(r"ymodem\r\n") == b"ymodem\r\n"
    # 经 load_profiles：YAML 单引号保留字面反斜杠，读回不得被破坏
    yaml_text = textwrap.dedent("""
        compiler_path: ./tools/comp.exe
        products:
          NEW-AI:
            protocol: custom_frame
            firmware_dir: ./products/NEW-AI/fwlib
            firmware_enter_cmd: 'C:\\fw\\lib'
            script_enter_cmd: 'C:\\fw\\lib'
    """)
    p = tmp_path / "products.yaml"; p.write_text(yaml_text)
    prof = load_profiles(p)["NEW-AI"]
    assert prof.firmware_enter_cmd == b"C:\\fw\\lib"
    assert prof.script_enter_cmd == b"C:\\fw\\lib"
