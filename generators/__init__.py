"""Composition root — wires all generator dependencies."""
from __future__ import annotations

from gdpc import Editor

from analysis.world_analysis import WorldAnalyser
from data.configurations import SettlementConfig, TerrainConfig
from planning.settlement_planner import SettlementPlanner
from generators.settlement_generator import SettlementGenerator
from utils.http_client import GDMCClient
from world_interface.terrain_loader import TerrainLoader


def create_generator(editor: Editor, client: GDMCClient) -> SettlementGenerator:
    """Build and wire a fully configured SettlementGenerator."""
    terrain_config    = TerrainConfig()
    settlement_config = SettlementConfig()
    terrain_loader    = TerrainLoader(client)
    analyser          = WorldAnalyser(
        terrain_loader=terrain_loader,
        configuration=terrain_config,
    )
    planner = SettlementPlanner(settlement_config)

    return SettlementGenerator(
        editor=editor,
        analyser=analyser,
        settlement_config=settlement_config,
        terrain_config=terrain_config,
        planner=planner
    )