"""
Godot Project Analyzer
Scans entire Godot projects for deep analysis.
Works completely offline - no Godot required.
"""

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

from .gdscript_parser import GDScriptParser, GDClass
from .tscn_parser import TscnParser, TscnScene


@dataclass
class ProjectInfo:
    path: str
    name: str
    config: dict = field(default_factory=dict)
    autoloads: list[dict] = field(default_factory=list)
    input_actions: list[str] = field(default_factory=list)


class ProjectAnalyzer:
    """Analyze entire Godot projects."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.gdscript_parser = GDScriptParser()
        self.tscn_parser = TscnParser()
        
        # Caches
        self._scripts: dict[str, GDClass] = {}
        self._scenes: dict[str, TscnScene] = {}
        self._project_info: Optional[ProjectInfo] = None
    
    def get_project_info(self) -> dict:
        """Get basic project information from project.godot."""
        if self._project_info:
            return self._info_to_dict(self._project_info)
        
        godot_file = self.project_path / "project.godot"
        if not godot_file.exists():
            return {"error": "No project.godot found"}
        
        content = godot_file.read_text(encoding='utf-8')
        
        info = ProjectInfo(
            path=str(self.project_path),
            name=self._extract_config_value(content, 'config/name') or "Unknown"
        )
        
        # Extract autoloads
        autoload_section = re.search(r'\[autoload\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if autoload_section:
            for match in re.finditer(r'(\w+)="?\*?res://(.+?)"?$', autoload_section.group(1), re.MULTILINE):
                info.autoloads.append({
                    "name": match.group(1),
                    "path": f"res://{match.group(2)}"
                })
        
        # Extract input actions
        input_section = re.search(r'\[input\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if input_section:
            for match in re.finditer(r'^(\w+)=', input_section.group(1), re.MULTILINE):
                info.input_actions.append(match.group(1))
        
        self._project_info = info
        return self._info_to_dict(info)
    
    def _extract_config_value(self, content: str, key: str) -> Optional[str]:
        """Extract a config value from project.godot."""
        match = re.search(rf'{key}="(.+?)"', content)
        return match.group(1) if match else None
    
    def _info_to_dict(self, info: ProjectInfo) -> dict:
        return {
            "path": info.path,
            "name": info.name,
            "autoloads": info.autoloads,
            "input_actions": info.input_actions
        }
    
    def scan_all_scripts(self) -> list[dict]:
        """Scan and parse all GDScript files in the project."""
        scripts = []
        for gd_file in self.project_path.rglob("*.gd"):
            # Skip addons unless specifically requested
            rel_path = gd_file.relative_to(self.project_path)
            try:
                gd_class = self.gdscript_parser.parse_file(gd_file)
                self._scripts[str(rel_path)] = gd_class
                scripts.append({
                    "path": str(rel_path),
                    "class_name": gd_class.name,
                    "extends": gd_class.extends,
                    "is_tool": gd_class.is_tool,
                    "function_count": len(gd_class.functions),
                    "signal_count": len(gd_class.signals),
                    "export_count": len(gd_class.exports)
                })
            except Exception as e:
                scripts.append({
                    "path": str(rel_path),
                    "error": str(e)
                })
        return scripts
    
    def scan_all_scenes(self) -> list[dict]:
        """Scan and parse all scene files in the project."""
        scenes = []
        for tscn_file in self.project_path.rglob("*.tscn"):
            rel_path = tscn_file.relative_to(self.project_path)
            try:
                scene = self.tscn_parser.parse_file(tscn_file)
                self._scenes[str(rel_path)] = scene
                scenes.append({
                    "path": str(rel_path),
                    "root_type": scene.root_node.type if scene.root_node else None,
                    "node_count": len(scene.nodes),
                    "connection_count": len(scene.connections),
                    "external_resources": len(scene.ext_resources)
                })
            except Exception as e:
                scenes.append({
                    "path": str(rel_path),
                    "error": str(e)
                })
        return scenes
    
    def find_nodes_by_type(self, node_type: str) -> list[dict]:
        """Find all nodes of a specific type across all scenes."""
        if not self._scenes:
            self.scan_all_scenes()
        
        results = []
        for scene_path, scene in self._scenes.items():
            for node in scene.nodes:
                if node.type and node_type.lower() in node.type.lower():
                    results.append({
                        "scene": scene_path,
                        "node_name": node.name,
                        "node_type": node.type,
                        "parent": node.parent,
                        "groups": node.groups
                    })
        return results
    
    def find_nodes_by_group(self, group_name: str) -> list[dict]:
        """Find all nodes in a specific group across all scenes."""
        if not self._scenes:
            self.scan_all_scenes()
        
        results = []
        for scene_path, scene in self._scenes.items():
            for node in scene.nodes:
                if group_name in node.groups:
                    results.append({
                        "scene": scene_path,
                        "node_name": node.name,
                        "node_type": node.type,
                        "groups": node.groups
                    })
        return results
    
    def find_script_usages(self, search_term: str) -> list[dict]:
        """Search for a term across all scripts (function names, variables, etc)."""
        if not self._scripts:
            self.scan_all_scripts()
        
        results = []
        search_lower = search_term.lower()
        
        for script_path, gd_class in self._scripts.items():
            matches = []
            
            # Check class name
            if gd_class.name and search_lower in gd_class.name.lower():
                matches.append({"type": "class_name", "name": gd_class.name})
            
            # Check functions
            for func in gd_class.functions:
                if search_lower in func.name.lower():
                    matches.append({
                        "type": "function",
                        "name": func.name,
                        "line": func.line
                    })
            
            # Check signals
            for sig in gd_class.signals:
                if search_lower in sig.name.lower():
                    matches.append({
                        "type": "signal",
                        "name": sig.name,
                        "line": sig.line
                    })
            
            # Check exports
            for exp in gd_class.exports:
                if search_lower in exp.name.lower():
                    matches.append({
                        "type": "export",
                        "name": exp.name,
                        "line": exp.line
                    })
            
            # Check variables
            for var in gd_class.variables:
                if search_lower in var.name.lower():
                    matches.append({
                        "type": "variable",
                        "name": var.name,
                        "line": var.line
                    })
            
            if matches:
                results.append({
                    "script": script_path,
                    "matches": matches
                })
        
        return results
    
    def find_signal_connections(self, signal_name: str) -> list[dict]:
        """Find all connections for a specific signal across scenes."""
        if not self._scenes:
            self.scan_all_scenes()
        
        results = []
        signal_lower = signal_name.lower()
        
        for scene_path, scene in self._scenes.items():
            for conn in scene.connections:
                if signal_lower in conn.signal.lower():
                    results.append({
                        "scene": scene_path,
                        "signal": conn.signal,
                        "from_node": conn.from_node,
                        "to_node": conn.to_node,
                        "method": conn.method
                    })
        
        return results
    
    def get_dependency_graph(self) -> dict:
        """Build a dependency graph of all scripts and scenes."""
        if not self._scripts:
            self.scan_all_scripts()
        if not self._scenes:
            self.scan_all_scenes()
        
        dependencies = defaultdict(list)
        
        # Script dependencies (preloads, loads)
        for script_path, gd_class in self._scripts.items():
            for dep in gd_class.preloads:
                dependencies[f"res://{script_path}"].append(dep)
        
        # Scene dependencies (external resources, instances)
        for scene_path, scene in self._scenes.items():
            for res in scene.ext_resources:
                if res.path:
                    dependencies[f"res://{scene_path}"].append(res.path)
            for node in scene.nodes:
                if node.instance:
                    # Find the actual path from ext_resources
                    for res in scene.ext_resources:
                        if res.id == node.instance:
                            dependencies[f"res://{scene_path}"].append(res.path)
        
        return dict(dependencies)
    
    def find_orphaned_resources(self) -> dict:
        """Find resources that aren't referenced anywhere."""
        deps = self.get_dependency_graph()
        
        # Flatten all dependencies
        all_referenced = set()
        for deps_list in deps.values():
            all_referenced.update(deps_list)
        
        # Find all resources
        all_scripts = {f"res://{p}" for p in self._scripts.keys()}
        all_scenes = {f"res://{p}" for p in self._scenes.keys()}
        
        # Find unreferenced (excluding autoloads)
        autoloads = set()
        info = self.get_project_info()
        for al in info.get("autoloads", []):
            autoloads.add(al["path"])
        
        orphaned_scripts = all_scripts - all_referenced - autoloads
        orphaned_scenes = all_scenes - all_referenced
        
        # Remove main scene
        # TODO: Check project.godot for main scene
        
        return {
            "orphaned_scripts": list(orphaned_scripts),
            "orphaned_scenes": list(orphaned_scenes)
        }
    
    def analyze_script(self, script_path: str) -> dict:
        """Get detailed analysis of a single script."""
        full_path = self.project_path / script_path
        if not full_path.exists():
            return {"error": f"Script not found: {script_path}"}
        
        gd_class = self.gdscript_parser.parse_file(full_path)
        return self.gdscript_parser.to_dict(gd_class)
    
    def analyze_scene(self, scene_path: str) -> dict:
        """Get detailed analysis of a single scene."""
        full_path = self.project_path / scene_path
        if not full_path.exists():
            return {"error": f"Scene not found: {scene_path}"}
        
        scene = self.tscn_parser.parse_file(full_path)
        result = self.tscn_parser.to_dict(scene)
        result["node_tree"] = self.tscn_parser.get_node_tree(scene)
        return result
    
    def search_in_files(self, pattern: str, file_types: list[str] = None) -> list[dict]:
        """Search for a regex pattern across project files."""
        if file_types is None:
            file_types = [".gd", ".tscn", ".tres"]
        
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        for file_type in file_types:
            for file_path in self.project_path.rglob(f"*{file_type}"):
                rel_path = file_path.relative_to(self.project_path)
                try:
                    content = file_path.read_text(encoding='utf-8')
                    matches = []
                    for i, line in enumerate(content.split('\n'), 1):
                        if regex.search(line):
                            matches.append({
                                "line": i,
                                "content": line.strip()[:200]  # Truncate long lines
                            })
                    if matches:
                        results.append({
                            "file": str(rel_path),
                            "matches": matches
                        })
                except Exception as e:
                    pass  # Skip unreadable files
        
        return results
