import argparse


def test_gui_entrypoint_is_available():
    import src.tkinter_app as tkinter_app

    parser = tkinter_app.build_arg_parser()
    args = parser.parse_args(["--gui"])
    assert args.gui is True

    assert hasattr(tkinter_app, "launch_gui")
    assert callable(tkinter_app.launch_gui)
