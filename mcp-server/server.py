"""
Godot MCP Server - Advanced Edition
Full-featured Godot editor integration + offline project analysis
"""

import asyncio
import json
import os
from typing import Any, Optional
from pathlib import Path

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from analyzers import ProjectAnalyzer, GDScriptParser, TscnParser

# ============ Configuration ============

GODOT_BRIDGE_URL = "http://127.0.0.1:6550"
DEFAULT_TIMEOUT = 30.0

server = Server("godot-mcp")

# Active project path (set via tool)
_active_project: Optional[str] = None
_analyzer: Optional[ProjectAnalyzer] = None


# ============ Godot HTTP Client ============

async def call_godot(endpoint: str, data: dict = None) -> dict:
    """Make HTTP request to Godot editor plugin."""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            url = f"{GODOT_BRIDGE_URL}/{endpoint}"
            if data:
                response = await client.post(url, json=data)
            else:
                response = await client.get(url)
            return response.json()
        except httpx.ConnectError:
            return {
                "error": "Cannot connect to Godot editor",
                "hint": "Make sure Godot is running with the Claude Bridge plugin enabled"
            }
        except Exception as e:
            return {"error": str(e)}


def get_analyzer() -> Optional[ProjectAnalyzer]:
    """Get the project analyzer for offline analysis."""
    global _analyzer, _active_project
    if _active_project and (not _analyzer or _analyzer.project_path != Path(_active_project)):
        _analyzer = ProjectAnalyzer(_active_project)
    return _analyzer


# ============ Tool Definitions ============

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # === Connection & Project ===
        Tool(
            name="godot_ping",
            description="Check if Godot editor is connected and responding",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="godot_set_project",
            description="Set the active Godot project path for offline analysis. Required before using analysis tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Absolute path to the Godot project folder (containing project.godot)"
                    }
                },
                "required": ["project_path"]
            }
        ),
        
        # === Scene Tree (Live) ===
        Tool(
            name="godot_get_scene_tree",
            description="Get the current scene's full node hierarchy from the running editor",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="godot_get_flat_nodes",
            description="Get a flat list of all nodes in the current scene with positions",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="godot_open_scene",
            description="Open a scene file in the editor",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string", "description": "Resource path (e.g., 'res://scenes/main.tscn')"}
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="godot_save_scene",
            description="Save the currently open scene",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # === Selection ===
        Tool(
            name="godot_get_selected",
            description="Get currently selected nodes in the editor",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="godot_select_nodes",
            description="Select nodes by their paths",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_paths": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["node_paths"]
            }
        ),
        Tool(
            name="godot_select_by_type",
            description="Select all nodes of a specific type",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Node type (e.g., 'MeshInstance3D', 'Area3D')"}
                },
                "required": ["type"]
            }
        ),
        Tool(
            name="godot_select_by_group",
            description="Select all nodes in a specific group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group": {"type": "string"}
                },
                "required": ["group"]
            }
        ),
        
        # === Node Creation ===
        Tool(
            name="godot_create_node",
            description="Create a new node in the scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_type": {"type": "string", "description": "Node class (e.g., 'Node3D', 'MeshInstance3D')"},
                    "node_name": {"type": "string"},
                    "parent_path": {"type": "string", "description": "Path to parent node, or '.' for root"},
                    "position": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z]"},
                    "rotation": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] in degrees"},
                    "scale": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z]"}
                },
                "required": ["node_type", "node_name"]
            }
        ),
        Tool(
            name="godot_create_many_nodes",
            description="Create multiple nodes at once",
            inputSchema={
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "node_type": {"type": "string"},
                                "node_name": {"type": "string"},
                                "parent_path": {"type": "string"},
                                "position": {"type": "array"},
                                "rotation": {"type": "array"},
                                "scale": {"type": "array"}
                            }
                        }
                    }
                },
                "required": ["nodes"]
            }
        ),
        Tool(
            name="godot_delete_node",
            description="Delete a node from the scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="godot_duplicate_node",
            description="Duplicate a node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "new_name": {"type": "string"},
                    "offset": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] offset"}
                },
                "required": ["node_path"]
            }
        ),
        
        # === Node Properties ===
        Tool(
            name="godot_get_properties",
            description="Get all properties of a node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "filter": {"type": "array", "items": {"type": "string"}, "description": "Only return these properties"}
                },
                "required": ["node_path"]
            }
        ),
        Tool(
            name="godot_set_property",
            description="Set a property on a node",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "property": {"type": "string"},
                    "value": {"description": "Value to set (arrays become Vector3/Color)"}
                },
                "required": ["node_path", "property", "value"]
            }
        ),
        Tool(
            name="godot_set_multiple_properties",
            description="Set multiple properties on a node at once",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "properties": {"type": "object", "description": "Dict of property_name: value"}
                },
                "required": ["node_path", "properties"]
            }
        ),
        
        # === Groups ===
        Tool(
            name="godot_add_to_group",
            description="Add a node to a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "group": {"type": "string"}
                },
                "required": ["node_path", "group"]
            }
        ),
        Tool(
            name="godot_remove_from_group",
            description="Remove a node from a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_path": {"type": "string"},
                    "group": {"type": "string"}
                },
                "required": ["node_path", "group"]
            }
        ),
        
        # === Scene Instantiation ===
        Tool(
            name="godot_instantiate_scene",
            description="Instantiate a packed scene into the current scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string", "description": "Resource path to .tscn"},
                    "parent_path": {"type": "string"},
                    "node_name": {"type": "string"},
                    "position": {"type": "array", "items": {"type": "number"}},
                    "rotation": {"type": "array", "items": {"type": "number"}},
                    "scale": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="godot_instantiate_many",
            description="Instantiate multiple copies of a scene",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string"},
                    "parent_path": {"type": "string"},
                    "instances": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "position": {"type": "array"},
                                "rotation": {"type": "array"},
                                "scale": {"type": "array"}
                            }
                        }
                    }
                },
                "required": ["scene_path", "instances"]
            }
        ),
        
        # === Terrain & Level Design ===
        Tool(
            name="godot_get_terrain_height",
            description="Get terrain height at a position via raycast",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "z": {"type": "number"}
                },
                "required": ["x", "z"]
            }
        ),
        Tool(
            name="godot_get_terrain_heights",
            description="Get terrain heights at multiple positions",
            inputSchema={
                "type": "object",
                "properties": {
                    "positions": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "Array of [x, z] positions"
                    }
                },
                "required": ["positions"]
            }
        ),
        Tool(
            name="godot_scatter_objects",
            description="Scatter objects randomly in an area with terrain alignment and slope filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string", "description": "Scene to scatter"},
                    "count": {"type": "integer", "description": "Number to place"},
                    "center": {"type": "array", "description": "[x, y, z] center point"},
                    "radius": {"type": "number", "description": "Scatter radius"},
                    "min_distance": {"type": "number", "description": "Minimum distance between objects"},
                    "max_slope": {"type": "number", "description": "Maximum terrain slope in degrees"},
                    "align_to_terrain": {"type": "boolean", "description": "Align to surface normal"},
                    "random_rotation_y": {"type": "boolean", "description": "Random Y rotation"},
                    "scale_range": {"type": "array", "description": "[min, max] scale range"},
                    "parent_path": {"type": "string"}
                },
                "required": ["scene_path", "count"]
            }
        ),
        Tool(
            name="godot_place_along_path",
            description="Place objects along a path/spline with optional terrain snapping",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string"},
                    "points": {"type": "array", "description": "Array of [x, y, z] waypoints"},
                    "spacing": {"type": "number", "description": "Distance between placements"},
                    "align_to_path": {"type": "boolean", "description": "Rotate to face path direction"},
                    "snap_to_terrain": {"type": "boolean"},
                    "parent_path": {"type": "string"}
                },
                "required": ["scene_path", "points"]
            }
        ),
        Tool(
            name="godot_place_grid",
            description="Place objects in a grid pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string"},
                    "origin": {"type": "array", "description": "[x, y, z]"},
                    "size_x": {"type": "integer"},
                    "size_z": {"type": "integer"},
                    "spacing": {"type": "number"},
                    "snap_to_terrain": {"type": "boolean"},
                    "parent_path": {"type": "string"}
                },
                "required": ["scene_path"]
            }
        ),
        
        # === Batch Operations ===
        Tool(
            name="godot_batch_set_property",
            description="Set a property on multiple nodes",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_paths": {"type": "array", "items": {"type": "string"}},
                    "property": {"type": "string"},
                    "value": {}
                },
                "required": ["node_paths", "property", "value"]
            }
        ),
        Tool(
            name="godot_batch_add_to_group",
            description="Add multiple nodes to a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_paths": {"type": "array", "items": {"type": "string"}},
                    "group": {"type": "string"}
                },
                "required": ["node_paths", "group"]
            }
        ),
        Tool(
            name="godot_batch_delete_by_type",
            description="Delete all nodes of a specific type",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string"}
                },
                "required": ["type"]
            }
        ),
        Tool(
            name="godot_batch_delete_by_group",
            description="Delete all nodes in a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group": {"type": "string"}
                },
                "required": ["group"]
            }
        ),
        Tool(
            name="godot_batch_replace_mesh",
            description="Replace a mesh resource across all MeshInstance3D nodes",
            inputSchema={
                "type": "object",
                "properties": {
                    "old_mesh_path": {"type": "string"},
                    "new_mesh_path": {"type": "string"}
                },
                "required": ["old_mesh_path", "new_mesh_path"]
            }
        ),
        
        # === Search ===
        Tool(
            name="godot_search_nodes",
            description="Search nodes by multiple criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Node type to match"},
                    "name_contains": {"type": "string", "description": "Name substring"},
                    "group": {"type": "string", "description": "Group membership"},
                    "has_property": {"type": "string", "description": "Property that must exist"}
                }
            }
        ),
        Tool(
            name="godot_find_by_type",
            description="Find all nodes of a type",
            inputSchema={
                "type": "object",
                "properties": {"type": {"type": "string"}},
                "required": ["type"]
            }
        ),
        Tool(
            name="godot_find_by_group",
            description="Find all nodes in a group",
            inputSchema={
                "type": "object",
                "properties": {"group": {"type": "string"}},
                "required": ["group"]
            }
        ),
        Tool(
            name="godot_find_by_name",
            description="Find nodes by name pattern",
            inputSchema={
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"]
            }
        ),
        
        # === Project (Live) ===
        Tool(
            name="godot_list_scenes",
            description="List all .tscn scene files in the project (via editor)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="godot_list_scripts",
            description="List all .gd script files in the project (via editor)",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # === Debug ===
        Tool(
            name="godot_run_scene",
            description="Run the current scene in the editor",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="godot_stop_running",
            description="Stop the running game",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # === Script Execution ===
        Tool(
            name="godot_execute",
            description="Execute arbitrary GDScript code in the editor. Has access to 'editor', 'scene_root', 'selection'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "GDScript code to execute"}
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="godot_execute_on_selected",
            description="Execute code on each selected node. Has access to 'node' (current node) and 'editor'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"]
            }
        ),
        
        # ========== OFFLINE ANALYSIS (No Godot Required) ==========
        
        Tool(
            name="analyze_project_info",
            description="Get project.godot info including autoloads and input actions (offline)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_scan_scripts",
            description="Scan all GDScript files in the project (offline)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_scan_scenes",
            description="Scan all scene files in the project (offline)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_script",
            description="Get detailed analysis of a single script file (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {"type": "string", "description": "Relative path from project root"}
                },
                "required": ["script_path"]
            }
        ),
        Tool(
            name="analyze_scene",
            description="Get detailed analysis of a single scene file (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "scene_path": {"type": "string", "description": "Relative path from project root"}
                },
                "required": ["scene_path"]
            }
        ),
        Tool(
            name="analyze_find_nodes_by_type",
            description="Find all nodes of a type across all scenes (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_type": {"type": "string"}
                },
                "required": ["node_type"]
            }
        ),
        Tool(
            name="analyze_find_nodes_by_group",
            description="Find all nodes in a group across all scenes (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string"}
                },
                "required": ["group_name"]
            }
        ),
        Tool(
            name="analyze_find_script_usages",
            description="Search for function/variable/signal names across all scripts (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {"type": "string"}
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="analyze_find_signal_connections",
            description="Find all connections for a signal across scenes (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "signal_name": {"type": "string"}
                },
                "required": ["signal_name"]
            }
        ),
        Tool(
            name="analyze_dependency_graph",
            description="Get dependency graph of scripts and scenes (offline)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_find_orphans",
            description="Find resources that aren't referenced anywhere (offline)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_search_in_files",
            description="Search for a regex pattern across project files (offline)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search"},
                    "file_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to search (default: .gd, .tscn, .tres)"
                    }
                },
                "required": ["pattern"]
            }
        ),
    ]


# ============ Tool Handler ============

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    global _active_project
    
    result = {}
    
    # === Project Setup ===
    if name == "godot_set_project":
        path = arguments["project_path"]
        if os.path.exists(os.path.join(path, "project.godot")):
            _active_project = path
            result = {"success": True, "project": path}
        else:
            result = {"error": f"No project.godot found in {path}"}
    
    # === Offline Analysis Tools ===
    elif name.startswith("analyze_"):
        analyzer = get_analyzer()
        if not analyzer:
            result = {"error": "No project set. Use godot_set_project first."}
        else:
            try:
                if name == "analyze_project_info":
                    result = analyzer.get_project_info()
                elif name == "analyze_scan_scripts":
                    result = {"scripts": analyzer.scan_all_scripts()}
                elif name == "analyze_scan_scenes":
                    result = {"scenes": analyzer.scan_all_scenes()}
                elif name == "analyze_script":
                    result = analyzer.analyze_script(arguments["script_path"])
                elif name == "analyze_scene":
                    result = analyzer.analyze_scene(arguments["scene_path"])
                elif name == "analyze_find_nodes_by_type":
                    result = {"nodes": analyzer.find_nodes_by_type(arguments["node_type"])}
                elif name == "analyze_find_nodes_by_group":
                    result = {"nodes": analyzer.find_nodes_by_group(arguments["group_name"])}
                elif name == "analyze_find_script_usages":
                    result = {"usages": analyzer.find_script_usages(arguments["search_term"])}
                elif name == "analyze_find_signal_connections":
                    result = {"connections": analyzer.find_signal_connections(arguments["signal_name"])}
                elif name == "analyze_dependency_graph":
                    result = {"dependencies": analyzer.get_dependency_graph()}
                elif name == "analyze_find_orphans":
                    result = analyzer.find_orphaned_resources()
                elif name == "analyze_search_in_files":
                    file_types = arguments.get("file_types")
                    result = {"matches": analyzer.search_in_files(arguments["pattern"], file_types)}
            except Exception as e:
                result = {"error": str(e)}
    
    # === Live Godot Tools ===
    else:
        # Map tool names to endpoints
        endpoint_map = {
            "godot_ping": "ping",
            "godot_get_scene_tree": "scene/tree",
            "godot_get_flat_nodes": "scene/tree/flat",
            "godot_open_scene": "scene/open",
            "godot_save_scene": "scene/save",
            "godot_get_selected": "editor/selected",
            "godot_select_nodes": "editor/select",
            "godot_select_by_type": "editor/select/by_type",
            "godot_select_by_group": "editor/select/by_group",
            "godot_create_node": "node/create",
            "godot_create_many_nodes": "node/create_many",
            "godot_delete_node": "node/delete",
            "godot_duplicate_node": "node/duplicate",
            "godot_get_properties": "node/properties",
            "godot_set_property": "node/set_property",
            "godot_set_multiple_properties": "node/set_properties",
            "godot_add_to_group": "node/add_to_group",
            "godot_remove_from_group": "node/remove_from_group",
            "godot_instantiate_scene": "scene/instantiate",
            "godot_instantiate_many": "scene/instantiate_many",
            "godot_get_terrain_height": "terrain/height",
            "godot_get_terrain_heights": "terrain/heights",
            "godot_scatter_objects": "placement/scatter",
            "godot_place_along_path": "placement/along_path",
            "godot_place_grid": "placement/grid",
            "godot_batch_set_property": "batch/set_property",
            "godot_batch_add_to_group": "batch/add_to_group",
            "godot_batch_delete_by_type": "batch/delete_by_type",
            "godot_batch_delete_by_group": "batch/delete_by_group",
            "godot_batch_replace_mesh": "batch/replace_mesh",
            "godot_search_nodes": "search/nodes",
            "godot_find_by_type": "search/by_type",
            "godot_find_by_group": "search/by_group",
            "godot_find_by_name": "search/by_name",
            "godot_list_scenes": "project/scenes",
            "godot_list_scripts": "project/scripts",
            "godot_run_scene": "debug/run_scene",
            "godot_stop_running": "debug/stop",
            "godot_execute": "execute",
            "godot_execute_on_selected": "execute/on_selected",
        }
        
        endpoint = endpoint_map.get(name)
        if endpoint:
            result = await call_godot(endpoint, arguments if arguments else None)
        else:
            result = {"error": f"Unknown tool: {name}"}
    
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


# ============ Main ============

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
