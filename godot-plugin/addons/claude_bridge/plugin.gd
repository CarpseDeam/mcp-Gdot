@tool
extends EditorPlugin
## Claude Bridge - Advanced Godot Editor Integration
## Provides HTTP API for AI-assisted game development

const PORT = 6550
const MAX_CLIENTS = 10

var _server: TCPServer
var _clients: Array[StreamPeerTCP] = []
var _timer: Timer

# ============ Plugin Lifecycle ============

func _enter_tree() -> void:
	_server = TCPServer.new()
	var err = _server.listen(PORT, "127.0.0.1")
	if err != OK:
		push_error("Claude Bridge: Failed to start server on port %d (error %d)" % [PORT, err])
		return
	
	print("✨ Claude Bridge: Server listening on http://127.0.0.1:%d" % PORT)
	
	_timer = Timer.new()
	_timer.wait_time = 0.016  # ~60fps polling
	_timer.timeout.connect(_poll)
	add_child(_timer)
	_timer.start()


func _exit_tree() -> void:
	if _timer:
		_timer.stop()
		_timer.queue_free()
	if _server:
		_server.stop()
	for client in _clients:
		client.disconnect_from_host()
	_clients.clear()
	print("Claude Bridge: Server stopped")


func _poll() -> void:
	while _server.is_connection_available() and _clients.size() < MAX_CLIENTS:
		var client = _server.take_connection()
		_clients.append(client)
	
	var to_remove: Array[int] = []
	for i in range(_clients.size()):
		var client = _clients[i]
		client.poll()
		
		match client.get_status():
			StreamPeerTCP.STATUS_CONNECTED:
				if client.get_available_bytes() > 0:
					var request_data = client.get_utf8_string(client.get_available_bytes())
					if request_data.length() > 0:
						_handle_request(client, request_data)
						to_remove.append(i)
			StreamPeerTCP.STATUS_NONE, StreamPeerTCP.STATUS_ERROR:
				to_remove.append(i)
	
	for i in range(to_remove.size() - 1, -1, -1):
		_clients.remove_at(to_remove[i])


# ============ HTTP Request Handling ============

func _handle_request(client: StreamPeerTCP, request: String) -> void:
	var lines = request.split("\r\n")
	if lines.size() == 0:
		_send_error(client, 400, "Bad Request")
		return
	
	var request_line = lines[0].split(" ")
	if request_line.size() < 2:
		_send_error(client, 400, "Bad Request")
		return
	
	var method = request_line[0]
	var path = request_line[1]
	
	# Extract JSON body
	var body = ""
	var body_start = request.find("\r\n\r\n")
	if body_start != -1:
		body = request.substr(body_start + 4)
	
	var json_data = {}
	if body.length() > 0:
		var json = JSON.new()
		if json.parse(body) == OK:
			json_data = json.data if json.data is Dictionary else {}
	
	var response = _route_request(path.trim_prefix("/"), method, json_data)
	_send_json_response(client, response)


func _route_request(path: String, method: String, data: Dictionary) -> Dictionary:
	match path:
		# === Core ===
		"ping": return _ping()
		"editor/info": return _get_editor_info()
		
		# === Scene Tree ===
		"scene/tree": return _get_scene_tree()
		"scene/tree/flat": return _get_flat_node_list()
		"scene/open": return _open_scene(data)
		"scene/save": return _save_scene()
		"scene/new": return _new_scene(data)
		
		# === Selection ===
		"editor/selected": return _get_selected_nodes()
		"editor/select": return _select_nodes(data)
		"editor/select/by_type": return _select_by_type(data)
		"editor/select/by_group": return _select_by_group(data)
		
		# === Node Operations ===
		"node/create": return _create_node(data)
		"node/create_many": return _create_many_nodes(data)
		"node/delete": return _delete_node(data)
		"node/delete_many": return _delete_many_nodes(data)
		"node/duplicate": return _duplicate_node(data)
		"node/reparent": return _reparent_node(data)
		"node/properties": return _get_node_properties(data)
		"node/set_property": return _set_node_property(data)
		"node/set_properties": return _set_multiple_properties(data)
		"node/add_to_group": return _add_to_group(data)
		"node/remove_from_group": return _remove_from_group(data)
		
		# === Scene Instantiation ===
		"scene/instantiate": return _instantiate_scene(data)
		"scene/instantiate_many": return _instantiate_many(data)
		
		# === Level Design / Placement ===
		"terrain/height": return _get_terrain_height(data)
		"terrain/heights": return _get_terrain_heights(data)
		"terrain/normal": return _get_terrain_normal(data)
		"terrain/raycast": return _terrain_raycast(data)
		"placement/scatter": return _scatter_objects(data)
		"placement/along_path": return _place_along_path(data)
		"placement/grid": return _place_grid(data)
		
		# === Batch Operations ===
		"batch/set_property": return _batch_set_property(data)
		"batch/add_to_group": return _batch_add_to_group(data)
		"batch/delete_by_type": return _batch_delete_by_type(data)
		"batch/delete_by_group": return _batch_delete_by_group(data)
		"batch/replace_mesh": return _batch_replace_mesh(data)
		
		# === Search ===
		"search/nodes": return _search_nodes(data)
		"search/by_type": return _find_by_type(data)
		"search/by_group": return _find_by_group(data)
		"search/by_name": return _find_by_name(data)
		
		# === Project ===
		"project/scenes": return _list_project_scenes()
		"project/scripts": return _list_project_scripts()
		"project/resources": return _list_resources(data)
		
		# === Debug / Runtime ===
		"debug/run_scene": return _run_current_scene()
		"debug/stop": return _stop_running()
		
		# === Advanced ===
		"execute": return _execute_script(data)
		"execute/on_selected": return _execute_on_selected(data)
		
		_:
			return {"error": "Unknown endpoint: " + path, "available": _list_endpoints()}


func _list_endpoints() -> Array:
	return [
		"ping", "editor/info",
		"scene/tree", "scene/tree/flat", "scene/open", "scene/save", "scene/new",
		"editor/selected", "editor/select", "editor/select/by_type", "editor/select/by_group",
		"node/create", "node/create_many", "node/delete", "node/delete_many",
		"node/duplicate", "node/reparent", "node/properties", "node/set_property",
		"node/set_properties", "node/add_to_group", "node/remove_from_group",
		"scene/instantiate", "scene/instantiate_many",
		"terrain/height", "terrain/heights", "terrain/normal", "terrain/raycast",
		"placement/scatter", "placement/along_path", "placement/grid",
		"batch/set_property", "batch/add_to_group", "batch/delete_by_type",
		"batch/delete_by_group", "batch/replace_mesh",
		"search/nodes", "search/by_type", "search/by_group", "search/by_name",
		"project/scenes", "project/scripts", "project/resources",
		"debug/run_scene", "debug/stop",
		"execute", "execute/on_selected"
	]


# ============ Core Handlers ============

func _ping() -> Dictionary:
	return {
		"status": "ok",
		"message": "Claude Bridge connected!",
		"godot_version": Engine.get_version_info(),
		"plugin_version": "2.0.0"
	}


func _get_editor_info() -> Dictionary:
	var scene_root = EditorInterface.get_edited_scene_root()
	return {
		"current_scene": scene_root.scene_file_path if scene_root else null,
		"editor_scale": EditorInterface.get_editor_scale(),
		"is_playing": EditorInterface.is_playing_scene()
	}


# ============ Scene Tree Handlers ============

func _get_scene_tree() -> Dictionary:
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	return {"tree": _node_to_dict_recursive(root)}


func _node_to_dict_recursive(node: Node, max_depth: int = 50) -> Dictionary:
	if max_depth <= 0:
		return {"name": node.name, "truncated": true}
	
	var result = {
		"name": node.name,
		"type": node.get_class(),
		"path": str(node.get_path()),
		"children": []
	}
	
	if node is Node3D:
		result["position"] = _vec3_to_array(node.global_position)
	
	for child in node.get_children():
		result["children"].append(_node_to_dict_recursive(child, max_depth - 1))
	
	return result


func _get_flat_node_list() -> Dictionary:
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = []
	_collect_nodes_flat(root, nodes)
	return {"nodes": nodes, "count": nodes.size()}


func _collect_nodes_flat(node: Node, result: Array) -> void:
	var info = {
		"name": node.name,
		"type": node.get_class(),
		"path": str(node.get_path())
	}
	if node is Node3D:
		info["position"] = _vec3_to_array(node.global_position)
	result.append(info)
	
	for child in node.get_children():
		_collect_nodes_flat(child, result)


func _open_scene(data: Dictionary) -> Dictionary:
	if not data.has("scene_path"):
		return {"error": "Missing scene_path"}
	EditorInterface.open_scene_from_path(data["scene_path"])
	return {"success": true, "opened": data["scene_path"]}


func _save_scene() -> Dictionary:
	EditorInterface.save_scene()
	return {"success": true}


func _new_scene(data: Dictionary) -> Dictionary:
	var root_type = data.get("root_type", "Node3D")
	var root = ClassDB.instantiate(root_type)
	if not root:
		return {"error": "Invalid root type: " + root_type}
	root.name = data.get("name", "Root")
	
	var scene = PackedScene.new()
	scene.pack(root)
	
	if data.has("save_path"):
		ResourceSaver.save(scene, data["save_path"])
		EditorInterface.open_scene_from_path(data["save_path"])
	
	return {"success": true}


# ============ Selection Handlers ============

func _get_selected_nodes() -> Dictionary:
	var selection = EditorInterface.get_selection()
	var selected = selection.get_selected_nodes()
	var result = []
	for node in selected:
		var info = {
			"name": node.name,
			"type": node.get_class(),
			"path": str(node.get_path())
		}
		if node is Node3D:
			info["position"] = _vec3_to_array(node.global_position)
			info["rotation"] = _vec3_to_array(node.rotation_degrees)
			info["scale"] = _vec3_to_array(node.scale)
		result.append(info)
	return {"selected": result, "count": result.size()}


func _select_nodes(data: Dictionary) -> Dictionary:
	if not data.has("node_paths"):
		return {"error": "Missing node_paths"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var selection = EditorInterface.get_selection()
	selection.clear()
	
	var selected = []
	for path in data["node_paths"]:
		var node = root.get_node_or_null(path)
		if node:
			selection.add_node(node)
			selected.append(path)
	
	return {"selected": selected, "count": selected.size()}


func _select_by_type(data: Dictionary) -> Dictionary:
	if not data.has("type"):
		return {"error": "Missing type"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = _find_nodes_by_type_recursive(root, data["type"])
	var selection = EditorInterface.get_selection()
	selection.clear()
	
	var paths = []
	for node in nodes:
		selection.add_node(node)
		paths.append(str(node.get_path()))
	
	return {"selected": paths, "count": paths.size()}


func _select_by_group(data: Dictionary) -> Dictionary:
	if not data.has("group"):
		return {"error": "Missing group"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = _find_nodes_in_group_recursive(root, data["group"])
	var selection = EditorInterface.get_selection()
	selection.clear()
	
	var paths = []
	for node in nodes:
		selection.add_node(node)
		paths.append(str(node.get_path()))
	
	return {"selected": paths, "count": paths.size()}


# ============ Node Operations ============

func _create_node(data: Dictionary) -> Dictionary:
	if not data.has("node_type") or not data.has("node_name"):
		return {"error": "Missing node_type or node_name"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var parent = root
	if data.has("parent_path") and data["parent_path"] != ".":
		parent = root.get_node_or_null(data["parent_path"])
		if not parent:
			return {"error": "Parent not found: " + data["parent_path"]}
	
	var node = ClassDB.instantiate(data["node_type"])
	if not node:
		return {"error": "Failed to create: " + data["node_type"]}
	
	node.name = data["node_name"]
	parent.add_child(node)
	node.owner = root
	
	# Set initial properties
	if data.has("position") and node is Node3D:
		node.global_position = _array_to_vec3(data["position"])
	if data.has("rotation") and node is Node3D:
		node.rotation_degrees = _array_to_vec3(data["rotation"])
	if data.has("scale") and node is Node3D:
		node.scale = _array_to_vec3(data["scale"])
	if data.has("properties"):
		for prop in data["properties"]:
			node.set(prop, data["properties"][prop])
	
	return {"success": true, "path": str(node.get_path())}


func _create_many_nodes(data: Dictionary) -> Dictionary:
	if not data.has("nodes"):
		return {"error": "Missing nodes array"}
	
	var created = []
	for node_data in data["nodes"]:
		var result = _create_node(node_data)
		if result.has("path"):
			created.append(result["path"])
	
	return {"created": created, "count": created.size()}


func _delete_node(data: Dictionary) -> Dictionary:
	if not data.has("node_path"):
		return {"error": "Missing node_path"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	if data["node_path"] == "." or data["node_path"] == str(root.get_path()):
		return {"error": "Cannot delete scene root"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found: " + data["node_path"]}
	
	node.queue_free()
	return {"success": true}


func _delete_many_nodes(data: Dictionary) -> Dictionary:
	if not data.has("node_paths"):
		return {"error": "Missing node_paths"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var deleted = []
	for path in data["node_paths"]:
		var node = root.get_node_or_null(path)
		if node and node != root:
			node.queue_free()
			deleted.append(path)
	
	return {"deleted": deleted, "count": deleted.size()}


func _duplicate_node(data: Dictionary) -> Dictionary:
	if not data.has("node_path"):
		return {"error": "Missing node_path"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found"}
	
	var dupe = node.duplicate()
	if data.has("new_name"):
		dupe.name = data["new_name"]
	
	node.get_parent().add_child(dupe)
	dupe.owner = root
	_set_owner_recursive(dupe, root)
	
	if data.has("offset") and dupe is Node3D:
		dupe.global_position += _array_to_vec3(data["offset"])
	
	return {"success": true, "path": str(dupe.get_path())}


func _reparent_node(data: Dictionary) -> Dictionary:
	if not data.has("node_path") or not data.has("new_parent_path"):
		return {"error": "Missing node_path or new_parent_path"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	var new_parent = root.get_node_or_null(data["new_parent_path"])
	
	if not node:
		return {"error": "Node not found"}
	if not new_parent:
		return {"error": "New parent not found"}
	
	var global_pos = node.global_position if node is Node3D else null
	node.reparent(new_parent)
	node.owner = root
	if global_pos and data.get("keep_global_position", true):
		node.global_position = global_pos
	
	return {"success": true, "new_path": str(node.get_path())}


func _get_node_properties(data: Dictionary) -> Dictionary:
	if not data.has("node_path"):
		return {"error": "Missing node_path"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found"}
	
	var filter = data.get("filter", [])
	var properties = {}
	
	for prop in node.get_property_list():
		if not (prop["usage"] & PROPERTY_USAGE_EDITOR):
			continue
		if filter.size() > 0 and not prop["name"] in filter:
			continue
		
		var value = node.get(prop["name"])
		properties[prop["name"]] = _serialize_value(value)
	
	return {"properties": properties, "type": node.get_class()}


func _set_node_property(data: Dictionary) -> Dictionary:
	if not data.has("node_path") or not data.has("property") or not data.has("value"):
		return {"error": "Missing node_path, property, or value"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found"}
	
	var value = _deserialize_value(data["value"], node.get(data["property"]))
	node.set(data["property"], value)
	
	return {"success": true}


func _set_multiple_properties(data: Dictionary) -> Dictionary:
	if not data.has("node_path") or not data.has("properties"):
		return {"error": "Missing node_path or properties"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found"}
	
	for prop_name in data["properties"]:
		var current = node.get(prop_name)
		var value = _deserialize_value(data["properties"][prop_name], current)
		node.set(prop_name, value)
	
	return {"success": true}


func _add_to_group(data: Dictionary) -> Dictionary:
	if not data.has("node_path") or not data.has("group"):
		return {"error": "Missing node_path or group"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found"}
	
	node.add_to_group(data["group"], true)
	return {"success": true}


func _remove_from_group(data: Dictionary) -> Dictionary:
	if not data.has("node_path") or not data.has("group"):
		return {"error": "Missing node_path or group"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var node = root.get_node_or_null(data["node_path"])
	if not node:
		return {"error": "Node not found"}
	
	node.remove_from_group(data["group"])
	return {"success": true}


# ============ Scene Instantiation ============

func _instantiate_scene(data: Dictionary) -> Dictionary:
	if not data.has("scene_path"):
		return {"error": "Missing scene_path"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var packed = load(data["scene_path"])
	if not packed:
		return {"error": "Failed to load scene: " + data["scene_path"]}
	
	var instance = packed.instantiate()
	if data.has("node_name"):
		instance.name = data["node_name"]
	
	var parent = root
	if data.has("parent_path") and data["parent_path"] != ".":
		parent = root.get_node_or_null(data["parent_path"])
		if not parent:
			return {"error": "Parent not found"}
	
	parent.add_child(instance)
	instance.owner = root
	_set_owner_recursive(instance, root)
	
	if data.has("position") and instance is Node3D:
		instance.global_position = _array_to_vec3(data["position"])
	if data.has("rotation") and instance is Node3D:
		instance.rotation_degrees = _array_to_vec3(data["rotation"])
	if data.has("scale") and instance is Node3D:
		instance.scale = _array_to_vec3(data["scale"])
	
	return {"success": true, "path": str(instance.get_path())}


func _instantiate_many(data: Dictionary) -> Dictionary:
	if not data.has("scene_path") or not data.has("instances"):
		return {"error": "Missing scene_path or instances"}
	
	var packed = load(data["scene_path"])
	if not packed:
		return {"error": "Failed to load scene"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var parent = root
	if data.has("parent_path") and data["parent_path"] != ".":
		parent = root.get_node_or_null(data["parent_path"])
		if not parent:
			return {"error": "Parent not found"}
	
	var created = []
	for inst_data in data["instances"]:
		var instance = packed.instantiate()
		if inst_data.has("name"):
			instance.name = inst_data["name"]
		
		parent.add_child(instance)
		instance.owner = root
		_set_owner_recursive(instance, root)
		
		if inst_data.has("position") and instance is Node3D:
			instance.global_position = _array_to_vec3(inst_data["position"])
		if inst_data.has("rotation") and instance is Node3D:
			instance.rotation_degrees = _array_to_vec3(inst_data["rotation"])
		if inst_data.has("scale") and instance is Node3D:
			instance.scale = _array_to_vec3(inst_data["scale"])
		
		created.append(str(instance.get_path()))
	
	return {"created": created, "count": created.size()}


# ============ Level Design / Terrain ============

func _get_terrain_height(data: Dictionary) -> Dictionary:
	if not data.has("x") or not data.has("z"):
		return {"error": "Missing x or z coordinate"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var space = root.get_world_3d().direct_space_state
	var from = Vector3(data["x"], 10000, data["z"])
	var to = Vector3(data["x"], -10000, data["z"])
	
	var query = PhysicsRayQueryParameters3D.create(from, to)
	var result = space.intersect_ray(query)
	
	if result:
		return {
			"height": result.position.y,
			"normal": _vec3_to_array(result.normal),
			"position": _vec3_to_array(result.position)
		}
	return {"height": 0, "hit": false}


func _get_terrain_heights(data: Dictionary) -> Dictionary:
	if not data.has("positions"):
		return {"error": "Missing positions array"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var space = root.get_world_3d().direct_space_state
	var results = []
	
	for pos in data["positions"]:
		var from = Vector3(pos[0], 10000, pos[1])
		var to = Vector3(pos[0], -10000, pos[1])
		var query = PhysicsRayQueryParameters3D.create(from, to)
		var result = space.intersect_ray(query)
		
		if result:
			results.append({
				"x": pos[0], "z": pos[1],
				"height": result.position.y,
				"normal": _vec3_to_array(result.normal)
			})
		else:
			results.append({"x": pos[0], "z": pos[1], "height": 0, "hit": false})
	
	return {"results": results}


func _get_terrain_normal(data: Dictionary) -> Dictionary:
	if not data.has("x") or not data.has("z"):
		return {"error": "Missing x or z"}
	
	var height_result = _get_terrain_height(data)
	if height_result.has("normal"):
		return {"normal": height_result["normal"]}
	return {"error": "No terrain hit"}


func _terrain_raycast(data: Dictionary) -> Dictionary:
	if not data.has("from") or not data.has("to"):
		return {"error": "Missing from or to"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var space = root.get_world_3d().direct_space_state
	var query = PhysicsRayQueryParameters3D.create(
		_array_to_vec3(data["from"]),
		_array_to_vec3(data["to"])
	)
	
	if data.has("collision_mask"):
		query.collision_mask = data["collision_mask"]
	
	var result = space.intersect_ray(query)
	
	if result:
		return {
			"hit": true,
			"position": _vec3_to_array(result.position),
			"normal": _vec3_to_array(result.normal),
			"collider": str(result.collider.get_path()) if result.collider else null
		}
	return {"hit": false}


func _scatter_objects(data: Dictionary) -> Dictionary:
	if not data.has("scene_path") or not data.has("count"):
		return {"error": "Missing scene_path or count"}
	
	var packed = load(data["scene_path"])
	if not packed:
		return {"error": "Failed to load scene"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var center = _array_to_vec3(data.get("center", [0, 0, 0]))
	var radius = data.get("radius", 50.0)
	var count = data["count"]
	var min_distance = data.get("min_distance", 1.0)
	var align_to_terrain = data.get("align_to_terrain", true)
	var max_slope = data.get("max_slope", 45.0)
	var random_rotation_y = data.get("random_rotation_y", true)
	var scale_range = data.get("scale_range", [1.0, 1.0])
	
	var parent = root
	if data.has("parent_path") and data["parent_path"] != ".":
		parent = root.get_node_or_null(data["parent_path"])
		if not parent:
			return {"error": "Parent not found"}
	
	var space = root.get_world_3d().direct_space_state
	var placed_positions: Array[Vector3] = []
	var created = []
	var attempts = 0
	var max_attempts = count * 10
	
	while created.size() < count and attempts < max_attempts:
		attempts += 1
		
		# Random point in circle
		var angle = randf() * TAU
		var dist = sqrt(randf()) * radius
		var x = center.x + cos(angle) * dist
		var z = center.z + sin(angle) * dist
		
		# Check min distance
		var too_close = false
		for existing in placed_positions:
			if Vector2(x, z).distance_to(Vector2(existing.x, existing.z)) < min_distance:
				too_close = true
				break
		if too_close:
			continue
		
		# Raycast for height
		var from = Vector3(x, 10000, z)
		var to = Vector3(x, -10000, z)
		var query = PhysicsRayQueryParameters3D.create(from, to)
		var result = space.intersect_ray(query)
		
		if not result:
			continue
		
		# Check slope
		var slope = rad_to_deg(acos(result.normal.dot(Vector3.UP)))
		if slope > max_slope:
			continue
		
		# Create instance
		var instance = packed.instantiate()
		parent.add_child(instance)
		instance.owner = root
		_set_owner_recursive(instance, root)
		
		instance.global_position = result.position
		
		if align_to_terrain:
			# Align to surface normal
			var up = result.normal
			var forward = Vector3.FORWARD
			if abs(up.dot(forward)) > 0.99:
				forward = Vector3.RIGHT
			var right = up.cross(forward).normalized()
			forward = right.cross(up).normalized()
			instance.global_transform.basis = Basis(right, up, forward)
		
		if random_rotation_y:
			instance.rotate_y(randf() * TAU)
		
		var scale_factor = randf_range(scale_range[0], scale_range[1])
		instance.scale = Vector3.ONE * scale_factor
		
		placed_positions.append(result.position)
		created.append(str(instance.get_path()))
	
	return {
		"created": created,
		"count": created.size(),
		"attempts": attempts
	}


func _place_along_path(data: Dictionary) -> Dictionary:
	if not data.has("scene_path") or not data.has("points"):
		return {"error": "Missing scene_path or points"}
	
	var packed = load(data["scene_path"])
	if not packed:
		return {"error": "Failed to load scene"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var points: Array[Vector3] = []
	for p in data["points"]:
		points.append(_array_to_vec3(p))
	
	var spacing = data.get("spacing", 5.0)
	var align_to_path = data.get("align_to_path", true)
	var snap_to_terrain = data.get("snap_to_terrain", true)
	
	var parent = root
	if data.has("parent_path"):
		parent = root.get_node_or_null(data["parent_path"])
	
	var space = root.get_world_3d().direct_space_state
	var created = []
	
	# Walk along path
	var current_dist = 0.0
	for i in range(points.size() - 1):
		var start = points[i]
		var end = points[i + 1]
		var segment_length = start.distance_to(end)
		var direction = (end - start).normalized()
		
		while current_dist < segment_length:
			var pos = start + direction * current_dist
			
			if snap_to_terrain:
				var query = PhysicsRayQueryParameters3D.create(
					Vector3(pos.x, 10000, pos.z),
					Vector3(pos.x, -10000, pos.z)
				)
				var result = space.intersect_ray(query)
				if result:
					pos.y = result.position.y
			
			var instance = packed.instantiate()
			parent.add_child(instance)
			instance.owner = root
			_set_owner_recursive(instance, root)
			
			instance.global_position = pos
			
			if align_to_path:
				instance.look_at(pos + direction, Vector3.UP)
			
			created.append(str(instance.get_path()))
			current_dist += spacing
		
		current_dist -= segment_length
	
	return {"created": created, "count": created.size()}


func _place_grid(data: Dictionary) -> Dictionary:
	if not data.has("scene_path"):
		return {"error": "Missing scene_path"}
	
	var packed = load(data["scene_path"])
	if not packed:
		return {"error": "Failed to load scene"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var origin = _array_to_vec3(data.get("origin", [0, 0, 0]))
	var size_x = data.get("size_x", 10)
	var size_z = data.get("size_z", 10)
	var spacing = data.get("spacing", 5.0)
	var snap_to_terrain = data.get("snap_to_terrain", true)
	
	var parent = root
	if data.has("parent_path"):
		parent = root.get_node_or_null(data["parent_path"])
	
	var space = root.get_world_3d().direct_space_state
	var created = []
	
	for x in range(size_x):
		for z in range(size_z):
			var pos = origin + Vector3(x * spacing, 0, z * spacing)
			
			if snap_to_terrain:
				var query = PhysicsRayQueryParameters3D.create(
					Vector3(pos.x, 10000, pos.z),
					Vector3(pos.x, -10000, pos.z)
				)
				var result = space.intersect_ray(query)
				if result:
					pos.y = result.position.y
			
			var instance = packed.instantiate()
			parent.add_child(instance)
			instance.owner = root
			_set_owner_recursive(instance, root)
			
			instance.global_position = pos
			created.append(str(instance.get_path()))
	
	return {"created": created, "count": created.size()}


# ============ Batch Operations ============

func _batch_set_property(data: Dictionary) -> Dictionary:
	if not data.has("node_paths") or not data.has("property") or not data.has("value"):
		return {"error": "Missing node_paths, property, or value"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var modified = []
	for path in data["node_paths"]:
		var node = root.get_node_or_null(path)
		if node:
			var current = node.get(data["property"])
			var value = _deserialize_value(data["value"], current)
			node.set(data["property"], value)
			modified.append(path)
	
	return {"modified": modified, "count": modified.size()}


func _batch_add_to_group(data: Dictionary) -> Dictionary:
	if not data.has("node_paths") or not data.has("group"):
		return {"error": "Missing node_paths or group"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var modified = []
	for path in data["node_paths"]:
		var node = root.get_node_or_null(path)
		if node:
			node.add_to_group(data["group"], true)
			modified.append(path)
	
	return {"modified": modified, "count": modified.size()}


func _batch_delete_by_type(data: Dictionary) -> Dictionary:
	if not data.has("type"):
		return {"error": "Missing type"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = _find_nodes_by_type_recursive(root, data["type"])
	var deleted = []
	
	for node in nodes:
		if node != root:
			deleted.append(str(node.get_path()))
			node.queue_free()
	
	return {"deleted": deleted, "count": deleted.size()}


func _batch_delete_by_group(data: Dictionary) -> Dictionary:
	if not data.has("group"):
		return {"error": "Missing group"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = _find_nodes_in_group_recursive(root, data["group"])
	var deleted = []
	
	for node in nodes:
		if node != root:
			deleted.append(str(node.get_path()))
			node.queue_free()
	
	return {"deleted": deleted, "count": deleted.size()}


func _batch_replace_mesh(data: Dictionary) -> Dictionary:
	if not data.has("old_mesh_path") or not data.has("new_mesh_path"):
		return {"error": "Missing old_mesh_path or new_mesh_path"}
	
	var new_mesh = load(data["new_mesh_path"])
	if not new_mesh:
		return {"error": "Failed to load new mesh"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var replaced = []
	var mesh_instances = _find_nodes_by_type_recursive(root, "MeshInstance3D")
	
	for mi in mesh_instances:
		if mi.mesh and mi.mesh.resource_path == data["old_mesh_path"]:
			mi.mesh = new_mesh
			replaced.append(str(mi.get_path()))
	
	return {"replaced": replaced, "count": replaced.size()}


# ============ Search ============

func _search_nodes(data: Dictionary) -> Dictionary:
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var results = []
	_search_recursive(root, data, results)
	return {"results": results, "count": results.size()}


func _search_recursive(node: Node, criteria: Dictionary, results: Array) -> void:
	var match = true
	
	if criteria.has("type"):
		if not criteria["type"] in node.get_class():
			match = false
	
	if criteria.has("name_contains"):
		if not criteria["name_contains"].to_lower() in node.name.to_lower():
			match = false
	
	if criteria.has("group"):
		if not node.is_in_group(criteria["group"]):
			match = false
	
	if criteria.has("has_property"):
		if not node.get(criteria["has_property"]):
			match = false
	
	if match:
		var info = {
			"name": node.name,
			"type": node.get_class(),
			"path": str(node.get_path())
		}
		if node is Node3D:
			info["position"] = _vec3_to_array(node.global_position)
		results.append(info)
	
	for child in node.get_children():
		_search_recursive(child, criteria, results)


func _find_by_type(data: Dictionary) -> Dictionary:
	if not data.has("type"):
		return {"error": "Missing type"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = _find_nodes_by_type_recursive(root, data["type"])
	var results = []
	for node in nodes:
		results.append({
			"name": node.name,
			"type": node.get_class(),
			"path": str(node.get_path())
		})
	
	return {"results": results, "count": results.size()}


func _find_by_group(data: Dictionary) -> Dictionary:
	if not data.has("group"):
		return {"error": "Missing group"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var nodes = _find_nodes_in_group_recursive(root, data["group"])
	var results = []
	for node in nodes:
		results.append({
			"name": node.name,
			"type": node.get_class(),
			"path": str(node.get_path())
		})
	
	return {"results": results, "count": results.size()}


func _find_by_name(data: Dictionary) -> Dictionary:
	if not data.has("pattern"):
		return {"error": "Missing pattern"}
	
	var root = EditorInterface.get_edited_scene_root()
	if not root:
		return {"error": "No scene open"}
	
	var pattern = data["pattern"].to_lower()
	var results = []
	_find_by_name_recursive(root, pattern, results)
	
	return {"results": results, "count": results.size()}


func _find_by_name_recursive(node: Node, pattern: String, results: Array) -> void:
	if pattern in node.name.to_lower():
		results.append({
			"name": node.name,
			"type": node.get_class(),
			"path": str(node.get_path())
		})
	for child in node.get_children():
		_find_by_name_recursive(child, pattern, results)


# ============ Project Scanning ============

func _list_project_scenes() -> Dictionary:
	var scenes = []
	_scan_dir("res://", scenes, ".tscn")
	return {"scenes": scenes, "count": scenes.size()}


func _list_project_scripts() -> Dictionary:
	var scripts = []
	_scan_dir("res://", scripts, ".gd")
	return {"scripts": scripts, "count": scripts.size()}


func _list_resources(data: Dictionary) -> Dictionary:
	var extension = data.get("extension", ".tres")
	var resources = []
	_scan_dir("res://", resources, extension)
	return {"resources": resources, "count": resources.size()}


func _scan_dir(path: String, results: Array, extension: String) -> void:
	var dir = DirAccess.open(path)
	if not dir:
		return
	
	dir.list_dir_begin()
	var file_name = dir.get_next()
	
	while file_name != "":
		if dir.current_is_dir() and not file_name.begins_with("."):
			_scan_dir(path + file_name + "/", results, extension)
		elif file_name.ends_with(extension):
			results.append(path + file_name)
		file_name = dir.get_next()


# ============ Debug / Runtime ============

func _run_current_scene() -> Dictionary:
	EditorInterface.play_current_scene()
	return {"success": true}


func _stop_running() -> Dictionary:
	EditorInterface.stop_playing_scene()
	return {"success": true}


# ============ Script Execution ============

func _execute_script(data: Dictionary) -> Dictionary:
	if not data.has("code"):
		return {"error": "Missing code"}
	
	var script = GDScript.new()
	script.source_code = """
extends RefCounted

var editor: EditorInterface
var scene_root: Node
var selection: EditorSelection

func execute():
%s
""" % _indent(data["code"])
	
	var err = script.reload()
	if err != OK:
		return {"error": "Compilation failed", "code": err}
	
	var instance = script.new()
	instance.editor = EditorInterface
	instance.scene_root = EditorInterface.get_edited_scene_root()
	instance.selection = EditorInterface.get_selection()
	
	var result = instance.execute()
	
	if result != null:
		return {"result": _serialize_value(result)}
	return {"success": true}


func _execute_on_selected(data: Dictionary) -> Dictionary:
	if not data.has("code"):
		return {"error": "Missing code"}
	
	var selected = EditorInterface.get_selection().get_selected_nodes()
	if selected.size() == 0:
		return {"error": "No nodes selected"}
	
	var script = GDScript.new()
	script.source_code = """
extends RefCounted

var node: Node
var editor: EditorInterface

func execute():
%s
""" % _indent(data["code"])
	
	var err = script.reload()
	if err != OK:
		return {"error": "Compilation failed"}
	
	var results = []
	for node in selected:
		var instance = script.new()
		instance.node = node
		instance.editor = EditorInterface
		var result = instance.execute()
		results.append({
			"node": str(node.get_path()),
			"result": _serialize_value(result) if result != null else null
		})
	
	return {"results": results}


# ============ Utilities ============

func _vec3_to_array(v: Vector3) -> Array:
	return [v.x, v.y, v.z]


func _array_to_vec3(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


func _indent(code: String) -> String:
	var lines = code.split("\n")
	var result = []
	for line in lines:
		result.append("\t" + line)
	return "\n".join(result)


func _set_owner_recursive(node: Node, owner: Node) -> void:
	for child in node.get_children():
		child.owner = owner
		_set_owner_recursive(child, owner)


func _find_nodes_by_type_recursive(node: Node, type: String) -> Array[Node]:
	var results: Array[Node] = []
	if type.to_lower() in node.get_class().to_lower():
		results.append(node)
	for child in node.get_children():
		results.append_array(_find_nodes_by_type_recursive(child, type))
	return results


func _find_nodes_in_group_recursive(node: Node, group: String) -> Array[Node]:
	var results: Array[Node] = []
	if node.is_in_group(group):
		results.append(node)
	for child in node.get_children():
		results.append_array(_find_nodes_in_group_recursive(child, group))
	return results


func _serialize_value(value: Variant) -> Variant:
	if value is Vector3:
		return {"_type": "Vector3", "value": _vec3_to_array(value)}
	if value is Vector2:
		return {"_type": "Vector2", "value": [value.x, value.y]}
	if value is Color:
		return {"_type": "Color", "value": [value.r, value.g, value.b, value.a]}
	if value is Transform3D:
		return {"_type": "Transform3D", "origin": _vec3_to_array(value.origin)}
	if value is NodePath:
		return {"_type": "NodePath", "value": str(value)}
	if value is Resource:
		return {"_type": "Resource", "path": value.resource_path}
	if value is Object:
		return {"_type": "Object", "class": value.get_class()}
	if value is Array:
		var arr = []
		for item in value:
			arr.append(_serialize_value(item))
		return arr
	return value


func _deserialize_value(value: Variant, hint: Variant = null) -> Variant:
	if value is Array:
		if hint is Vector3:
			return Vector3(value[0], value[1], value[2])
		if hint is Vector2:
			return Vector2(value[0], value[1])
		if hint is Color:
			return Color(value[0], value[1], value[2], value[3] if value.size() > 3 else 1.0)
		if value.size() == 3 and hint == null:
			return Vector3(value[0], value[1], value[2])
	return value


# ============ HTTP Helpers ============

func _send_json_response(client: StreamPeerTCP, data: Dictionary) -> void:
	var json_str = JSON.stringify(data)
	var response = "HTTP/1.1 200 OK\r\n"
	response += "Content-Type: application/json\r\n"
	response += "Content-Length: %d\r\n" % json_str.length()
	response += "Access-Control-Allow-Origin: *\r\n"
	response += "Connection: close\r\n"
	response += "\r\n"
	response += json_str
	client.put_data(response.to_utf8_buffer())


func _send_error(client: StreamPeerTCP, code: int, message: String) -> void:
	var response = "HTTP/1.1 %d %s\r\nConnection: close\r\n\r\n" % [code, message]
	client.put_data(response.to_utf8_buffer())
