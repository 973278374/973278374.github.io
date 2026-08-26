# Blender 资产管线（可选）

Mac M4 上用 Blender（Apple Silicon）做：

1. 导入 DXF/SVG 平面或按 `map.geojson` 手工描墙  
2. 墙体拉伸高度约 3 m，货架先用立方体阵列  
3. 导出 **glTF 2.0** 到 `godot/assets/warehouse.glb`  
4. 在 Godot 中实例化，替换默认 Floor 盒子  

离线宣传片：Cycles 渲染；实时演示仍用 Godot。

不使用 CUDA；Blender 在 Apple Silicon 上走 Metal。
