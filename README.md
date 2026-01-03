# Godot MCP - Advanced AI Bridge

🎮 **Full-featured Godot editor integration + offline project analysis for AI-assisted game development**

This MCP server gives Claude (or any MCP-compatible AI) the ability to:
- **Manipulate the Godot editor in real-time** - create nodes, modify scenes, place objects
- **Understand your project offline** - analyze scripts, find dependencies, search code
- **Level design at scale** - scatter objects, terrain-aware placement, batch operations

## Architecture

```
┌─────────────┐           ┌─────────────────────────────────────────┐
│             │           │            MCP Server (Python)          │
│   Claude    │◄─stdio───►│  ┌─────────────┐  ┌─────────────────┐   │
│             │           │  │ Live Tools  │  │ Offline Analysis│   │
└─────────────┘           │  │ (HTTP→Godot)│  │ (File Parsing)  │   │
                          │  └──────┬──────┘  └─────────────────┘   │
                          └─────────┼───────────────────────────────┘
                                    │ HTTP :6550
                          ┌─────────▼───────────┐
                          │   Godot Editor      │
                          │   Claude Bridge     │
                          │   (@tool plugin)    │
                          └─────────────────────┘
```

## Quick Start

### 1. Install the Godot Plugin

Copy `godot-plugin/addons/claude_bridge/` to your project:

```
your_project/
└── addons/
    └── claude_bridge/
        ├── plugin.cfg
        └── plugin.gd
```

Enable in: **Project → Project Settings → Plugins → Claude Bridge**

### 2. Install Python Dependencies

```bash
cd mcp-server
pip install -r requirements.txt
```

### 3. Configure Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "godot": {
      "command": "python",
      "args": ["C:\\Projects\\mcp-Gdot\\mcp-server\\server.py"]
    }
  }
}
```

Restart Claude Desktop.

---

## Tool Categories

### 🔌 Connection & Setup

| Tool | Description |
|------|-------------|
| `godot_ping` | Check if Godot is connected |
| `godot_set_project` | Set project path for offline analysis |

### 🌳 Scene Tree (Live)

| Tool | Description |
|------|-------------|
| `godot_get_scene_tree` | Get full node hierarchy |
| `godot_get_flat_nodes` | Flat list with positions |
| `godot_open_scene` | Open a scene file |
| `godot_save_scene` | Save current scene |

### 🎯 Selection

| Tool | Description |
|------|-------------|
| `godot_get_selected` | Get selected nodes |
| `godot_select_nodes` | Select by paths |
| `godot_select_by_type` | Select all of a type |
| `godot_select_by_group` | Select by group |

### ➕ Node Operations

| Tool | Description |
|------|-------------|
| `godot_create_node` | Create a node |
| `godot_create_many_nodes` | Batch create |
| `godot_delete_node` | Delete a node |
| `godot_duplicate_node` | Duplicate with offset |
| `godot_get_properties` | Read node properties |
| `godot_set_property` | Set a property |
| `godot_set_multiple_properties` | Set multiple at once |
| `godot_add_to_group` | Add to group |
| `godot_remove_from_group` | Remove from group |

### 📦 Scene Instantiation

| Tool | Description |
|------|-------------|
| `godot_instantiate_scene` | Instantiate a PackedScene |
| `godot_instantiate_many` | Batch instantiate |

### 🗺️ Level Design & Terrain

| Tool | Description |
|------|-------------|
| `godot_get_terrain_height` | Raycast for height at x,z |
| `godot_get_terrain_heights` | Batch height queries |
| `godot_scatter_objects` | Smart scatter with slope filtering |
| `godot_place_along_path` | Place along waypoints |
| `godot_place_grid` | Grid placement |

### ⚡ Batch Operations

| Tool | Description |
|------|-------------|
| `godot_batch_set_property` | Set property on multiple nodes |
| `godot_batch_add_to_group` | Add multiple to group |
| `godot_batch_delete_by_type` | Delete all of type |
| `godot_batch_delete_by_group` | Delete all in group |
| `godot_batch_replace_mesh` | Swap mesh resource project-wide |

### 🔍 Search

| Tool | Description |
|------|-------------|
| `godot_search_nodes` | Multi-criteria search |
| `godot_find_by_type` | Find by node type |
| `godot_find_by_group` | Find by group |
| `godot_find_by_name` | Find by name pattern |

### 🐛 Debug

| Tool | Description |
|------|-------------|
| `godot_run_scene` | Play current scene |
| `godot_stop_running` | Stop running game |

### 💻 Script Execution

| Tool | Description |
|------|-------------|
| `godot_execute` | Run arbitrary GDScript |
| `godot_execute_on_selected` | Run code on each selected node |

---

## Offline Analysis (No Godot Required!)

These tools parse your project files directly - Godot doesn't need to be running.

| Tool | Description |
|------|-------------|
| `analyze_project_info` | project.godot info, autoloads, inputs |
| `analyze_scan_scripts` | Scan all .gd files |
| `analyze_scan_scenes` | Scan all .tscn files |
| `analyze_script` | Deep analysis of one script |
| `analyze_scene` | Deep analysis of one scene |
| `analyze_find_nodes_by_type` | Find node types across all scenes |
| `analyze_find_nodes_by_group` | Find groups across all scenes |
| `analyze_find_script_usages` | Search for functions/variables/signals |
| `analyze_find_signal_connections` | Find signal connections |
| `analyze_dependency_graph` | Build dependency tree |
| `analyze_find_orphans` | Find unreferenced resources |
| `analyze_search_in_files` | Regex search across files |

---

## Example Prompts

### Level Design

```
"Scatter 100 oak trees in a 200m radius around the player spawn,
 avoid slopes over 30 degrees, minimum 5m spacing, random Y rotation"
```

```
"Place torches along the path from the entrance to the boss room,
 10 meters apart, aligned to face the path direction"
```

```
"Create a 5x5 grid of market stalls starting at (100, 0, 100)"
```

### Batch Operations

```
"Set all WildlifeSpawner nodes to respawn_time = 300"
```

```
"Delete all nodes in the 'debug' group"
```

```
"Replace all instances of old_tree.glb with new_tree.glb"
```

### Project Analysis

```
"Find all scripts that use the 'damage_dealt' signal"
```

```
"What functions does the PlayerCombat class have?"
```

```
"Show me the dependency graph - what loads what"
```

```
"Find orphaned scenes that aren't used anywhere"
```

### Custom Operations

```
"Run this code on all selected nodes: node.modulate = Color.RED"
```

```
"Execute: print(scene_root.get_children())"
```

---

## Extending the Plugin

### Adding a New Endpoint

1. Add handler in `plugin.gd`:

```gdscript
func _my_handler(data: Dictionary) -> Dictionary:
    # Do stuff
    return {"success": true, "data": result}
```

2. Add route in `_route_request()`:

```gdscript
"my/endpoint": return _my_handler(data)
```

3. Add tool in `server.py`:

```python
Tool(
    name="godot_my_tool",
    description="Does cool stuff",
    inputSchema={...}
)
```

4. Add to endpoint map in `call_tool()`.

---

## Troubleshooting

**"Cannot connect to Godot"**
- Is Godot running?
- Is the plugin enabled? Check Project Settings → Plugins
- Check Output panel for "Claude Bridge: Server listening..."

**Offline analysis not working**
- Did you call `godot_set_project` first?
- Is the path correct (should contain project.godot)?

**Terrain raycast returns no hits**
- Does your terrain have collision?
- Is the collision layer correct?

---

## License

MIT - Do whatever you want with it! 🚀
