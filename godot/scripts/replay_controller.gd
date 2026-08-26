extends Node3D
## 读取 Python 仿真导出的 trajectories.json，在本地回放 AGV。
## 地图坐标：仿真 x→Godot X，仿真 y→Godot Z（平面）。

@export var trajectory_path: String = "res://data/trajectories.json"
@export var nav_graph_path: String = "res://data/nav_graph.json"
@export var playback_speed: float = 8.0

var _frames: Array = []
var _by_vehicle: Dictionary = {}
var _meshes: Dictionary = {}
var _t: float = 0.0
var _t_max: float = 0.0
var _label: Label

func _ready() -> void:
	_label = $HUD/Label
	_load_nav_markers()
	_load_trajectories()
	set_process(true)

func _resolve(path: String) -> String:
	var abs_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(abs_path):
		return abs_path
	for alt in [path, "../data/output/trajectories.json", "../data/processed/nav_graph.json"]:
		if FileAccess.file_exists(alt):
			return alt
	return abs_path

func _load_nav_markers() -> void:
	var abs_path := _resolve(nav_graph_path)
	var text := FileAccess.get_file_as_string(abs_path)
	if text.is_empty():
		push_warning("nav_graph missing: %s" % abs_path)
		return
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		return
	var markers: Node3D = $Markers
	for n in data.get("nodes", []):
		var mi := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		var kind := str(n.get("kind", "junction"))
		if kind == "dock":
			mesh.size = Vector3(1.2, 0.4, 1.2)
		elif kind == "slot":
			mesh.size = Vector3(1.5, 0.3, 1.5)
		else:
			mesh.size = Vector3(0.3, 0.1, 0.3)
		mi.mesh = mesh
		mi.position = Vector3(float(n["x"]), 0.2, float(n["y"]))
		markers.add_child(mi)

func _load_trajectories() -> void:
	var abs_path := _resolve(trajectory_path)
	var text := FileAccess.get_file_as_string(abs_path)
	if text.is_empty():
		_label.text = "未找到 trajectories.json，请先运行 ./scripts/run_demo.sh"
		return
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_ARRAY:
		_label.text = "trajectories 格式错误"
		return
	_frames = data
	for row in _frames:
		var vid := str(row["vehicle_id"])
		if not _by_vehicle.has(vid):
			_by_vehicle[vid] = []
			var body := MeshInstance3D.new()
			var box := BoxMesh.new()
			box.size = Vector3(0.9, 0.5, 0.6)
			body.mesh = box
			$Vehicles.add_child(body)
			_meshes[vid] = body
		_by_vehicle[vid].append(row)
		_t_max = maxf(_t_max, float(row["t"]))
	_label.text = "Replay t=0 / %.0f  vehicles=%d  (speed=%.1fx)" % [_t_max, _by_vehicle.size(), playback_speed]

func _process(delta: float) -> void:
	if _frames.is_empty():
		return
	_t += delta * playback_speed
	if _t > _t_max:
		_t = 0.0
	for vid in _by_vehicle.keys():
		var samples: Array = _by_vehicle[vid]
		var pose := _sample_pose(samples, _t)
		var node: MeshInstance3D = _meshes[vid]
		node.position = Vector3(pose.x, 0.4, pose.y)
	_label.text = "Replay t=%.1f / %.0f  vehicles=%d  (speed=%.1fx, no CUDA)" % [_t, _t_max, _by_vehicle.size(), playback_speed]

func _sample_pose(samples: Array, t: float) -> Vector2:
	if samples.is_empty():
		return Vector2.ZERO
	if t <= float(samples[0]["t"]):
		return Vector2(float(samples[0]["x"]), float(samples[0]["y"]))
	for i in range(1, samples.size()):
		var a = samples[i - 1]
		var b = samples[i]
		var ta := float(a["t"])
		var tb := float(b["t"])
		if t <= tb:
			var u := 0.0 if tb <= ta else (t - ta) / (tb - ta)
			return Vector2(
				lerp(float(a["x"]), float(b["x"]), u),
				lerp(float(a["y"]), float(b["y"]), u)
			)
	var last = samples[samples.size() - 1]
	return Vector2(float(last["x"]), float(last["y"]))
