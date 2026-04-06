"""Main entry point: connect to Minecraft and run settlement generation."""
from __future__ import annotations

import logging
import sys

from gdpc import Editor

from generators import create_generator
from utils.http_client import GDMCClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    client = GDMCClient()
    if not client.check_connection():
        logger.error("Could not connect to GDMC HTTP Interface. Is Minecraft running?")
        return 1

    logger.info("Connection OK.")

    try:
        editor    = Editor(buffering=True)
        generator = create_generator(editor, client)
        state     = generator.generate()

        logger.info("--- SETTLEMENT SUMMARY ---")
        logger.info("  Districts : %d", len(state.districts.district_list))
        logger.info("  Road cells: %d", state.road_cell_count)
        logger.info("  Plots     : %d", state.plot_count)
        logger.info("  Buildings : %d", state.building_count)

    except KeyboardInterrupt:
        logger.warning("Generation cancelled by user.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())