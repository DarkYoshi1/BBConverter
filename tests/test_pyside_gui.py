import argparse


def test_gui_entrypoint_is_available():
    import src.pyside_app as pyside_app

    parser = pyside_app.build_arg_parser()
    args = parser.parse_args(["--gui"])
    assert args.gui is True

    assert hasattr(pyside_app, "launch_gui")
    assert callable(pyside_app.launch_gui)


def test_default_output_for_matches_cli_convention():
    import src.pyside_app as pyside_app

    assert pyside_app._default_output_for("") == ""
    assert pyside_app._default_output_for("/tmp/MyMod").endswith("MyMod_Release")
