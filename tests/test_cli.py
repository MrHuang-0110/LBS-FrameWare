from lbs_firmware_studio.cli import main


def test_cli_lists_products(monkeypatch, tmp_path, capsys):
    yaml = """
compiler_path: ./tools/rust-msc-latest-win10.exe
products:
  NEW-AI: {protocol: custom_frame, folders: [app], firmware_dir: ., script_dirs: {}, chunk_size: 248}
"""
    p = tmp_path / "products.yaml"; p.write_text(yaml)
    rc = main(["--config", str(p), "--list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "NEW-AI" in out
