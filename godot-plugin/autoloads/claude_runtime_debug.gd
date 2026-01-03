extends Node
## Claude Runtime Debug - Captures screenshots from running game
## Add as autoload: Project Settings > Autoload > claude_runtime_debug.gd

const PORT = 6551
const MAX_REQUEST_SIZE = 4096

var _server: TCPServer
var _client: StreamPeerTCP

func _ready() -> void:
	if not OS.is_debug_build():
		queue_free()
		return
	
	_server = TCPServer.new()
	var err = _server.listen(PORT, "127.0.0.1")
	if err != OK:
		push_error("Claude Runtime Debug: Failed to start on port %d" % PORT)
		return
	
	print("Claude Runtime Debug: Listening on port %d" % PORT)


func _process(_delta: float) -> void:
	if not _server:
		return
	
	if _server.is_connection_available():
		_client = _server.take_connection()
	
	if _client:
		_client.poll()
		if _client.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			if _client.get_available_bytes() > 0:
				var request = _client.get_utf8_string(min(_client.get_available_bytes(), MAX_REQUEST_SIZE))
				_handle_request(request)
				_client = null


func _handle_request(request: String) -> void:
	var path = _parse_path(request)
	var data = _parse_body(request)
	
	var response = {}
	match path:
		"ping":
			response = {"status": "ok", "message": "Game running!", "scene": get_tree().current_scene.name if get_tree().current_scene else null}
		"screenshot":
			response = await _take_screenshot(data)
		"info":
			response = _get_game_info()
		_:
			response = {"error": "Unknown endpoint", "available": ["ping", "screenshot", "info"]}
	
	_send_response(response)


func _take_screenshot(data: Dictionary) -> Dictionary:
	var viewport = get_viewport()
	if not viewport:
		return {"error": "No viewport available"}
	
	await RenderingServer.frame_post_draw
	
	var image = viewport.get_texture().get_image()
	if not image:
		return {"error": "Could not capture image"}
	
	var width = data.get("width", 0)
	var height = data.get("height", 0)
	
	if width > 0 and height > 0:
		image.resize(width, height, Image.INTERPOLATE_LANCZOS)
	elif width > 0 or height > 0:
		var aspect = float(image.get_width()) / float(image.get_height())
		if width > 0:
			height = int(width / aspect)
		else:
			width = int(height * aspect)
		image.resize(width, height, Image.INTERPOLATE_LANCZOS)
	
	var png_buffer = image.save_png_to_buffer()
	var base64_data = Marshalls.raw_to_base64(png_buffer)
	
	return {
		"success": true,
		"image_base64": base64_data,
		"width": image.get_width(),
		"height": image.get_height(),
		"format": "png"
	}


func _get_game_info() -> Dictionary:
	var scene = get_tree().current_scene
	return {
		"current_scene": scene.scene_file_path if scene else null,
		"scene_name": scene.name if scene else null,
		"fps": Engine.get_frames_per_second(),
		"viewport_size": [get_viewport().size.x, get_viewport().size.y],
		"is_debug": OS.is_debug_build()
	}


func _parse_path(request: String) -> String:
	var lines = request.split("\r\n")
	if lines.size() == 0:
		return ""
	var parts = lines[0].split(" ")
	if parts.size() < 2:
		return ""
	return parts[1].trim_prefix("/")


func _parse_body(request: String) -> Dictionary:
	var body_start = request.find("\r\n\r\n")
	if body_start == -1:
		return {}
	var body = request.substr(body_start + 4)
	if body.length() == 0:
		return {}
	var json = JSON.new()
	if json.parse(body) == OK and json.data is Dictionary:
		return json.data
	return {}


func _send_response(data: Dictionary) -> void:
	if not _client:
		return
	var json_str = JSON.stringify(data)
	var response = "HTTP/1.1 200 OK\r\n"
	response += "Content-Type: application/json\r\n"
	response += "Content-Length: %d\r\n" % json_str.length()
	response += "Connection: close\r\n"
	response += "\r\n"
	response += json_str
	_client.put_data(response.to_utf8_buffer())
