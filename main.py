import logging
from typing import Sequence

from src.app.bootstrap import setup_logging
from src.app.cli import parse_args
from src.app.workflow import execute_porting

logger = logging.getLogger("main")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)

    try:
        return execute_porting(args, logger)
    except KeyboardInterrupt:
        logger.warning("\nOperation cancelled by user")
        return 130
    except Exception as exc:
        logger.error(f"An error occurred during porting: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
