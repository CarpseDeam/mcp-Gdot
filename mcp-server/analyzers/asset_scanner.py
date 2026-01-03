"""
Asset Scanner & Organizer
Fast scanning and intelligent categorization of Godot project assets.
Creates a searchable index with metadata, tags, and categories.
"""

import os
import re
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import time


@dataclass
class AssetInfo:
    path: str
    type: str  # mesh, texture, scene, audio, material, script, resource
    pack: Optional[str] = None  # Detected asset pack
    category: Optional[str] = None  # trees, ruins, characters, etc.
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# Known asset pack detection patterns
ASSET_PACK_PATTERNS = {
    "triforge": ["triforge", "tri_forge", "tri-forge"],
    "synty": ["synty", "polygon"],
    "quaternius": ["quaternius", "lowpoly_animals", "ultimate_animals"],
    "kaykit": ["kaykit", "kay_kit"],
    "kenney": ["kenney"],
    "mixamo": ["mixamo"],
}

# Category detection from path/filename
CATEGORY_PATTERNS = {
    "trees": ["tree", "oak", "pine", "birch", "willow", "forest"],
    "rocks": ["rock", "stone", "boulder", "cliff"],
    "ruins": ["ruin", "ancient", "broken", "destroyed", "debris"],
    "buildings": ["house", "building", "tower", "castle", "wall", "door", "window", "roof"],
    "props": ["prop", "crate", "barrel", "chest", "table", "chair", "bench", "pot", "bucket"],
    "vegetation": ["grass", "bush", "shrub", "plant", "flower", "fern", "moss", "vine"],
    "characters": ["character", "player", "npc", "enemy", "human", "humanoid"],
    "creatures": ["creature", "monster", "animal", "beast", "wolf", "deer", "bear", "dragon"],
    "weapons": ["weapon", "sword", "axe", "bow", "staff", "shield", "dagger"],
    "armor": ["armor", "helmet", "chest", "boots", "gloves", "cape"],
    "effects": ["effect", "particle", "vfx", "fx", "magic", "spell"],
    "terrain": ["terrain", "ground", "floor", "path", "road"],
    "water": ["water", "lake", "river", "pond", "ocean", "wave"],
    "sky": ["sky", "cloud", "sun", "moon", "star"],
    "ui": ["ui", "gui", "hud", "icon", "button", "panel"],
    "audio": ["sfx", "music", "ambient", "sound"],
}

# File type mappings
FILE_TYPE_MAP = {
    # 3D Models
    ".glb": "mesh",
    ".gltf": "mesh",
    ".obj": "mesh",
    ".fbx": "mesh",
    ".dae": "mesh",
    ".blend": "mesh",
    # Textures
    ".png": "texture",
    ".jpg": "texture",
    ".jpeg": "texture",
    ".webp": "texture",
    ".svg": "texture",
    ".tga": "texture",
    ".bmp": "texture",
    ".exr": "texture",
    ".hdr": "texture",
    # Scenes
    ".tscn": "scene",
    # Scripts
    ".gd": "script",
    # Resources
    ".tres": "resource",
    ".res": "resource",
    # Materials
    ".material": "material",
    ".shader": "shader",
    ".gdshader": "shader",
    # Audio
    ".wav": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    # Fonts
    ".ttf": "font",
    ".otf": "font",
    # Animation
    ".anim": "animation",
}


class AssetScanner:
    """Scans and indexes Godot project assets."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.cache_file = self.project_path / ".godot" / "claude_asset_cache.json"
        self.assets: dict[str, AssetInfo] = {}
        self.categories: dict[str, list[str]] = defaultdict(list)
        self.packs: dict[str, list[str]] = defaultdict(list)
        self.by_type: dict[str, list[str]] = defaultdict(list)
        self._scan_time = 0
    
    def scan(self, force: bool = False, exclude_addons: bool = False) -> dict:
        """
        Scan all assets in the project.
        Returns summary statistics.
        """
        # Check cache
        if not force and self._load_cache():
            return self._get_summary()
        
        start = time.time()
        self.assets.clear()
        self.categories.clear()
        self.packs.clear()
        self.by_type.clear()
        
        # Walk project directory
        for file_path in self.project_path.rglob("*"):
            if file_path.is_dir():
                continue
            
            # Skip hidden and Godot internal
            rel_path = file_path.relative_to(self.project_path)
            rel_str = str(rel_path)
            
            if rel_str.startswith("."):
                continue
            if ".godot" in rel_str:
                continue
            if exclude_addons and rel_str.startswith("addons"):
                continue
            
            # Get file type
            ext = file_path.suffix.lower()
            asset_type = FILE_TYPE_MAP.get(ext)
            
            if not asset_type:
                continue
            
            # Create asset info
            res_path = f"res://{rel_str.replace(os.sep, '/')}"
            asset = AssetInfo(
                path=res_path,
                type=asset_type
            )
            
            # Detect asset pack
            asset.pack = self._detect_pack(rel_str)
            
            # Detect category
            asset.category = self._detect_category(rel_str, file_path.stem)
            
            # Generate tags
            asset.tags = self._generate_tags(rel_str, file_path.stem)
            
            # Type-specific metadata
            if asset_type == "mesh":
                asset.metadata = self._get_mesh_metadata(file_path)
            elif asset_type == "scene":
                asset.metadata = self._get_scene_metadata(file_path)
            elif asset_type == "texture":
                asset.metadata = self._get_texture_metadata(file_path)
            
            # Store asset
            self.assets[res_path] = asset
            self.by_type[asset_type].append(res_path)
            
            if asset.pack:
                self.packs[asset.pack].append(res_path)
            if asset.category:
                self.categories[asset.category].append(res_path)
        
        self._scan_time = time.time() - start
        self._save_cache()
        
        return self._get_summary()
    
    def _detect_pack(self, path: str) -> Optional[str]:
        """Detect which asset pack this file belongs to."""
        path_lower = path.lower()
        for pack_name, patterns in ASSET_PACK_PATTERNS.items():
            for pattern in patterns:
                if pattern in path_lower:
                    return pack_name
        return None
    
    def _detect_category(self, path: str, filename: str) -> Optional[str]:
        """Detect asset category from path and filename."""
        combined = f"{path}/{filename}".lower()
        
        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in combined:
                    return category
        return None
    
    def _generate_tags(self, path: str, filename: str) -> list[str]:
        """Generate searchable tags from path and filename."""
        tags = set()
        
        # Split path into components
        parts = path.lower().replace("\\", "/").split("/")
        parts.append(filename.lower())
        
        for part in parts:
            # Remove common prefixes/suffixes
            clean = re.sub(r'^(sm_|sk_|t_|m_|mat_|tex_)', '', part)
            clean = re.sub(r'(_lod\d+|_\d+|_mat|_diff|_norm|_ao|_rough|_metal)$', '', clean)
            
            # Split by underscore and camelCase
            words = re.split(r'[_\-\s]', clean)
            for word in words:
                # Also split camelCase
                camel_split = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)
                if camel_split:
                    tags.update(w.lower() for w in camel_split if len(w) > 2)
                elif len(word) > 2:
                    tags.add(word)
        
        # Remove common non-descriptive words
        stop_words = {'res', 'assets', 'asset', 'models', 'model', 'textures', 'texture', 
                      'materials', 'scenes', 'prefabs', 'prefab', 'import', 'source'}
        tags -= stop_words
        
        return list(tags)
    
    def _get_mesh_metadata(self, file_path: Path) -> dict:
        """Get metadata for mesh files."""
        metadata = {"size_bytes": file_path.stat().st_size}
        
        # Check for LOD variants
        stem = file_path.stem
        parent = file_path.parent
        lod_files = list(parent.glob(f"{stem}_lod*.glb")) + list(parent.glob(f"{stem}_LOD*.glb"))
        metadata["has_lods"] = len(lod_files) > 0
        metadata["lod_count"] = len(lod_files)
        
        return metadata
    
    def _get_scene_metadata(self, file_path: Path) -> dict:
        """Get metadata for scene files."""
        metadata = {"size_bytes": file_path.stat().st_size}
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Count nodes
            node_matches = re.findall(r'\[node name="', content)
            metadata["node_count"] = len(node_matches)
            
            # Get root type
            root_match = re.search(r'\[node name="\w+" type="(\w+)"\]', content)
            if root_match:
                metadata["root_type"] = root_match.group(1)
            
            # Check for scripts
            metadata["has_script"] = 'script = ' in content or '.gd"' in content
            
        except Exception:
            pass
        
        return metadata
    
    def _get_texture_metadata(self, file_path: Path) -> dict:
        """Get metadata for texture files."""
        metadata = {"size_bytes": file_path.stat().st_size}
        
        # Detect texture type from naming
        name_lower = file_path.stem.lower()
        if any(x in name_lower for x in ['_diff', '_albedo', '_color', '_basecolor']):
            metadata["texture_type"] = "diffuse"
        elif any(x in name_lower for x in ['_norm', '_normal', '_nrm']):
            metadata["texture_type"] = "normal"
        elif any(x in name_lower for x in ['_rough', '_roughness']):
            metadata["texture_type"] = "roughness"
        elif any(x in name_lower for x in ['_metal', '_metallic']):
            metadata["texture_type"] = "metallic"
        elif any(x in name_lower for x in ['_ao', '_ambient', '_occlusion']):
            metadata["texture_type"] = "ao"
        elif any(x in name_lower for x in ['_height', '_disp', '_displacement']):
            metadata["texture_type"] = "height"
        elif any(x in name_lower for x in ['_emiss', '_emission', '_glow']):
            metadata["texture_type"] = "emission"
        else:
            metadata["texture_type"] = "unknown"
        
        return metadata
    
    def _get_summary(self) -> dict:
        """Get scan summary statistics."""
        return {
            "total_assets": len(self.assets),
            "by_type": {k: len(v) for k, v in self.by_type.items()},
            "by_pack": {k: len(v) for k, v in self.packs.items()},
            "by_category": {k: len(v) for k, v in self.categories.items()},
            "scan_time_seconds": round(self._scan_time, 2)
        }
    
    def _save_cache(self) -> None:
        """Save scan results to cache file."""
        cache_data = {
            "version": 1,
            "scan_time": self._scan_time,
            "assets": {
                path: {
                    "type": asset.type,
                    "pack": asset.pack,
                    "category": asset.category,
                    "tags": asset.tags,
                    "metadata": asset.metadata
                }
                for path, asset in self.assets.items()
            }
        }
        
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(cache_data, indent=2))
        except Exception:
            pass  # Cache is optional
    
    def _load_cache(self) -> bool:
        """Load from cache if valid."""
        if not self.cache_file.exists():
            return False
        
        try:
            cache_data = json.loads(self.cache_file.read_text())
            
            if cache_data.get("version") != 1:
                return False
            
            # Rebuild from cache
            for path, data in cache_data["assets"].items():
                asset = AssetInfo(
                    path=path,
                    type=data["type"],
                    pack=data.get("pack"),
                    category=data.get("category"),
                    tags=data.get("tags", []),
                    metadata=data.get("metadata", {})
                )
                self.assets[path] = asset
                self.by_type[asset.type].append(path)
                if asset.pack:
                    self.packs[asset.pack].append(path)
                if asset.category:
                    self.categories[asset.category].append(path)
            
            self._scan_time = cache_data.get("scan_time", 0)
            return True
            
        except Exception:
            return False
    
    # ============ Search Methods ============
    
    def search(self, 
               query: str = None,
               asset_type: str = None,
               pack: str = None,
               category: str = None,
               tags: list[str] = None,
               limit: int = 50) -> list[dict]:
        """Search assets with multiple filters."""
        results = []
        
        for path, asset in self.assets.items():
            # Filter by type
            if asset_type and asset.type != asset_type:
                continue
            
            # Filter by pack
            if pack and asset.pack != pack:
                continue
            
            # Filter by category
            if category and asset.category != category:
                continue
            
            # Filter by tags (all must match)
            if tags:
                if not all(t.lower() in asset.tags for t in tags):
                    continue
            
            # Filter by query (searches path and tags)
            if query:
                query_lower = query.lower()
                if query_lower not in path.lower() and not any(query_lower in t for t in asset.tags):
                    continue
            
            results.append({
                "path": path,
                "type": asset.type,
                "pack": asset.pack,
                "category": asset.category,
                "tags": asset.tags,
                "metadata": asset.metadata
            })
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_random(self,
                   asset_type: str = None,
                   pack: str = None,
                   category: str = None,
                   count: int = 1) -> list[str]:
        """Get random assets matching filters."""
        candidates = []
        for path, asset in self.assets.items():
            if asset_type and asset.type != asset_type:
                continue
            if pack and asset.pack != pack:
                continue
            if category and asset.category != category:
                continue
            candidates.append(path)
        
        if not candidates:
            return []
        
        return random.sample(candidates, min(count, len(candidates)))
    
    def list_packs(self) -> dict:
        """List all detected asset packs with counts."""
        return {pack: len(paths) for pack, paths in self.packs.items()}
    
    def list_categories(self) -> dict:
        """List all categories with counts."""
        return {cat: len(paths) for cat, paths in self.categories.items()}
    
    def get_asset(self, path: str) -> Optional[dict]:
        """Get detailed info for a single asset."""
        asset = self.assets.get(path)
        if not asset:
            return None
        return {
            "path": asset.path,
            "type": asset.type,
            "pack": asset.pack,
            "category": asset.category,
            "tags": asset.tags,
            "metadata": asset.metadata
        }
