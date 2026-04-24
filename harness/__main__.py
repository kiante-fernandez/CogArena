"""Entry point for `python -m harness`.

The harness package wraps the existing reference agents (random, browser-use)
under a single CLI so third-party evaluators can run them without writing
glue code. See `python -m harness --help`.
"""
from harness.cli import main

if __name__ == "__main__":
    main()
