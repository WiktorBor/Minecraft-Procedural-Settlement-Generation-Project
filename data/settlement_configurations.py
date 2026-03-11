from dataclasses import dataclass

@dataclass
class SettlementConfig:

    min_plot_distance: int = 12

    max_slope: float = 0.5
    max_roughness: float = 2

    min_water_distance: int = 4