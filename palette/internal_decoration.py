from __future__ import annotations
 
import json
import random
import hashlib
from pathlib import Path
from typing import Optional, Any
 
 
@dataclass
class FurnitureItem:
    """Single furniture piece definition."""
    block: str
    offset: tuple[int, int, int]  # (dx, dy, dz) relative to building origin
    properties: dict[str, Any]
    rotation: int = 0  # Can vary 0, 90, 180, 270
 
 
@dataclass
class FurnitureSet:
    """Collection of furniture items for a room."""
    name: str
    items: list[FurnitureItem]
    description: str = ""
 
 
class FurnitureLibrary:
    """
    Manages furniture sets and provides variance.
    
    Loads from furniture_library.json and provides methods for:
    - Selecting furniture sets for buildings
    - Randomizing placement offsets
    - Applying variant rotations per building instance
    """
    
    def __init__(self, library_path: Optional[str] = None):
        """
        Initialize furniture library.
        
        Parameters
        ----------
        library_path : str, optional
            Path to furniture_library.json
            If None, looks in current directory
        """
        
        self.sets: dict[str, FurnitureSet] = {}
        self._load_library(library_path)
    
    def _load_library(self, library_path: Optional[str]) -> None:
        """Load furniture sets from JSON."""
        
        if library_path is None:
            library_path = "furniture_library.json"
        
        try:
            with open(library_path, 'r') as f:
                data = json.load(f)
            
            for set_name, items in data.items():
                furniture_items = [
                    FurnitureItem(
                        block=item["block"],
                        offset=tuple(item["offset"]),
                        properties=item.get("properties", {}),
                    )
                    for item in items
                ]
                
                self.sets[set_name] = FurnitureSet(
                    name=set_name,
                    items=furniture_items,
                    description=f"Furniture set: {set_name}"
                )
        
        except FileNotFoundError:
            print(f"Warning: Furniture library not found at {library_path}")
            self.sets = {}
    
    def get_set(self, set_name: str) -> Optional[FurnitureSet]:
        """Get a furniture set by name."""
        return self.sets.get(set_name)
    
    def list_sets(self) -> list[str]:
        """List all available furniture set names."""
        return list(self.sets.keys())
    
    def select_set_for_building(
        self,
        building_type: str,
        available_sets: Optional[list[str]] = None,
        seed: Optional[int] = None,
    ) -> Optional[FurnitureSet]:
        """
        Select a furniture set for a building with optional seeding.
        
        Parameters
        ----------
        building_type : str
            Type of building (e.g., "cottage", "smithy")
        available_sets : list[str], optional
            List of valid set names for this building type
            If None, uses all available sets
        seed : int, optional
            Random seed for reproducibility
        
        Returns
        -------
        FurnitureSet or None
            Selected furniture set, or None if no valid sets
        """
        
        if seed is not None:
            random.seed(seed)
        
        if available_sets is None:
            available_sets = self._get_default_sets_for_type(building_type)
        
        # Filter to only available sets that exist in library
        valid_sets = [s for s in available_sets if s in self.sets]
        
        if not valid_sets:
            return None
        
        return random.choice(valid_sets)
    
    def _get_default_sets_for_type(self, building_type: str) -> list[str]:
        """Get default furniture sets for a building type."""
        
        defaults = {
            "residential": ["basic_living", "royal_bedroom", "kitchen"],
            "cottage": ["basic_living"],
            "manor": ["royal_bedroom"],
            "blacksmith": ["blacksmith_workshop"],
            "smithy": ["blacksmith_workshop"],
            "kitchen": ["kitchen"],
            "bedroom": ["royal_bedroom", "basic_living"],
            "workshop": ["blacksmith_workshop"],
        }
        
        return defaults.get(building_type, ["basic_living"])
    
    def apply_furniture_set(
        self,
        editor,
        set: FurnitureSet,
        building_x: int,
        building_y: int,
        building_z: int,
        seed: Optional[int] = None,
    ) -> None:
        """
        Place furniture from a set into the world.
        
        Parameters
        ----------
        editor : Editor
            World editor interface
        set : FurnitureSet
            Furniture set to place
        building_x, building_y, building_z : int
            Building origin coordinates
        seed : int, optional
            Seed for randomizing placement offsets
        """
        
        if seed is not None:
            random.seed(seed)
        
        for item in set.items:
            # Apply optional offset variance based on seed
            dx, dy, dz = item.offset
            
            if seed is not None:
                # Small random offset (±1 block) for variation
                dx += random.randint(-1, 1)
                dz += random.randint(-1, 1)
            
            x = building_x + dx
            y = building_y + dy
            z = building_z + dz
            
            # Apply rotation if seeded
            properties = dict(item.properties)
            if seed is not None and item.rotation > 0:
                # Apply rotation to block properties if applicable
                pass  # Implementation depends on specific blocks
            
            editor.placeBlock((x, y, z), Block(item.block, properties))
 
 
class BuildingVariant:
    """
    Per-building variation parameters.
    
    Each building gets unique variant parameters based on:
    - Building location (x, z)
    - District seed
    - Global settlement seed
    
    These determine:
    - Furniture set selection
    - Placement offsets
    - Accent color variation
    - Detail level
    """
    
    def __init__(
        self,
        building_x: int,
        building_z: int,
        district_seed: int,
        global_seed: int,
    ):
        """
        Initialize building variant parameters.
        
        Parameters
        ----------
        building_x, building_z : int
            Building world coordinates
        district_seed : int
            District-specific seed
        global_seed : int
            Settlement-wide seed
        """
        
        self.building_x = building_x
        self.building_z = building_z
        self.district_seed = district_seed
        self.global_seed = global_seed
        
        # Compute deterministic variant seed
        # Same location + seeds = same variant (reproducibility)
        self.variant_seed = self._compute_seed()
        
        # Pre-compute variance parameters
        self.furniture_variant = self.variant_seed % 100  # 0-99
        self.offset_variance = self.variant_seed % 10  # 0-9
        self.accent_variance = self.variant_seed % 5  # 0-4
        self.detail_variance = self.variant_seed % 3  # 0-2
    
    def _compute_seed(self) -> int:
        """
        Compute deterministic seed from building position and seeds.
        
        Uses hash to ensure:
        - Same location + same input seeds = same output seed
        - Different location = different output seed
        - Reversible if needed
        """
        
        combined = f"{self.building_x}{self.building_z}{self.district_seed}{self.global_seed}"
        hash_obj = hashlib.sha256(combined.encode())
        # Convert first 8 bytes of hash to integer
        return int(hash_obj.hexdigest()[:8], 16)
    
    def get_furniture_seed(self) -> int:
        """Get seed for furniture selection (0-99)."""
        return self.furniture_variant
    
    def get_placement_seed(self) -> int:
        """Get seed for placement offset variance (0-9)."""
        return self.offset_variance
    
    def get_accent_index(self, accent_pool: list[str]) -> str:
        """
        Get accent color/material from pool based on variance.
        
        Parameters
        ----------
        accent_pool : list[str]
            Available accent options
        
        Returns
        -------
        str
            Selected accent from pool
        """
        
        if not accent_pool:
            return "default"
        
        return accent_pool[self.accent_variance % len(accent_pool)]
    
    def should_add_detail(self, detail_level: str) -> bool:
        """
        Determine if extra detail should be added based on variance.
        
        Parameters
        ----------
        detail_level : str
            "simple", "moderate", "ornate"
        
        Returns
        -------
        bool
            True if detail should be added
        """
        
        if detail_level == "simple":
            return self.detail_variance >= 2  # 33% chance
        elif detail_level == "moderate":
            return self.detail_variance >= 1  # 67% chance
        else:  # ornate
            return True  # Always add details
 
 
class FurnitureVarianceManager:
    """
    Manages furniture variance across a settlement.
    
    Coordinates:
    - Loading furniture library
    - Per-building variant computation
    - Furniture set selection
    - Placement with variance
    """
    
    def __init__(
        self,
        library_path: Optional[str] = None,
        global_seed: Optional[int] = None,
    ):
        """
        Initialize variance manager.
        
        Parameters
        ----------
        library_path : str, optional
            Path to furniture_library.json
        global_seed : int, optional
            Global settlement seed for reproducibility
        """
        
        self.library = FurnitureLibrary(library_path)
        self.global_seed = global_seed or random.randint(0, 2**31 - 1)
        self.district_seed = random.randint(0, 2**31 - 1)
    
    def get_building_variant(
        self,
        building_x: int,
        building_z: int,
        district_index: Optional[int] = None,
    ) -> BuildingVariant:
        """
        Get variance parameters for a specific building.
        
        Parameters
        ----------
        building_x, building_z : int
            Building coordinates
        district_index : int, optional
            District the building belongs to (for seeding)
        
        Returns
        -------
        BuildingVariant
            Variance parameters for this building
        """
        
        district_seed = self.district_seed
        if district_index is not None:
            # Incorporate district into seed
            district_seed = self.district_seed ^ district_index
        
        return BuildingVariant(
            building_x=building_x,
            building_z=building_z,
            district_seed=district_seed,
            global_seed=self.global_seed,
        )
    
    def select_furniture_set(
        self,
        building_type: str,
        building_variant: BuildingVariant,
    ) -> Optional[FurnitureSet]:
        """
        Select furniture set for building using its variant.
        
        Parameters
        ----------
        building_type : str
            Type of building
        building_variant : BuildingVariant
            Variant parameters for this building
        
        Returns
        -------
        FurnitureSet or None
            Selected furniture set
        """
        
        available_sets = self.library._get_default_sets_for_type(building_type)
        
        return self.library.select_set_for_building(
            building_type=building_type,
            available_sets=available_sets,
            seed=building_variant.get_furniture_seed(),
        )
    
    def apply_furniture_with_variance(
        self,
        editor,
        building_type: str,
        building_x: int,
        building_y: int,
        building_z: int,
        district_index: Optional[int] = None,
    ) -> bool:
        """
        Apply furniture to a building with full variance.
        
        Single method that handles:
        1. Computing variant parameters
        2. Selecting furniture set
        3. Placing furniture with offsets
        
        Parameters
        ----------
        editor : Editor
            World editor
        building_type : str
            Type of building
        building_x, building_y, building_z : int
            Building coordinates
        district_index : int, optional
            District index
        
        Returns
        -------
        bool
            True if furniture was placed, False otherwise
        """
        
        # Get variant for this building
        variant = self.get_building_variant(building_x, building_z, district_index)
        
        # Select furniture set
        furniture_set = self.select_furniture_set(building_type, variant)
        
        if furniture_set is None:
            return False
        
        # Apply furniture
        self.library.apply_furniture_set(
            editor=editor,
            set=furniture_set,
            building_x=building_x,
            building_y=building_y,
            building_z=building_z,
            seed=variant.get_placement_seed(),
        )
        
        return True
 
 
# Helper to make dataclass work without importing
from dataclasses import dataclass
from typing import Any as BlockType
 
# Assume Block class exists
class Block:
    def __init__(self, name: str, properties: dict = None):
        self.name = name
        self.properties = properties or {}