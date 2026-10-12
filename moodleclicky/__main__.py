import sys

if "--apply-setup" in sys.argv:  # installers: save settings without loading any UI (no Tk needed)
    from moodleclicky.setup_cli import main as apply_main

    sys.exit(apply_main())

from moodleclicky.app import main  # noqa: E402

if __name__ == "__main__":
    main()
