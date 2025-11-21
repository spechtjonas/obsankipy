"""Script for adding cards to Anki from Obsidian."""

import logging
from pathlib import Path

import yaml

from ankimd.config_parser import NewConfig
from ankimd.run import run
from ankimd.utils.helpers import setup_cli_parser, setup_root_logger


def main():
    """Main functionality of script."""

    args = setup_cli_parser()
    setup_root_logger(args.debug)
    logger = logging.getLogger(__name__)
    logger.info("Starting script")
    try:
        config_path = Path(args.config_path)
        with open(config_path, "r", encoding="UTF-8") as f:
            config = yaml.safe_load(f)
        new_config = NewConfig.from_dict(config, base_dir=config_path.parent)
    except Exception as err:
        logger.error(f"Error parsing config file: {err}")
        raise Exception(f"Error parsing config file: {err}") from err

    run(new_config)


if __name__ == "__main__":
    main()
