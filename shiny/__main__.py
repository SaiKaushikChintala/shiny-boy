import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from shiny.launcher import needs_relaunch, relaunch

    if needs_relaunch():
        sys.exit(relaunch())
    from shiny.app.window import main

    sys.exit(main())
