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


def test_cli_defaults_config_to_base_dir(tmp_path, monkeypatch, capsys):
    import lbs_firmware_studio.cli as cli
    yaml_text = "compiler_path: ./c.exe\nproducts:\n  NEW-AI:\n    protocol: custom_frame\n"
    (tmp_path / "products.yaml").write_text(yaml_text)
    monkeypatch.setattr(cli, "base_dir", lambda: tmp_path)
    rc = cli.main(["--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "NEW-AI" in out
