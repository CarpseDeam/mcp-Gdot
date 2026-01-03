"""
TSCN Scene Parser
Parses Godot .tscn files to extract node structure, resources, and connections.
Works completely offline - no Godot required.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class TscnResource:
    id: str
    type: str
    path: Optional[str] = None  # For ext_resource
    properties: dict = field(default_factory=dict)


@dataclass
class TscnNode:
    name: str
    type: Optional[str] = None
    parent: Optional[str] = None
    instance: Optional[str] = None  # For instanced scenes
    properties: dict = field(default_factory=dict)
    groups: list[str] = field(default_factory=list)
    children: list['TscnNode'] = field(default_factory=list)


@dataclass
class TscnConnection:
    signal: str
    from_node: str
    to_node: str
    method: str
    flags: int = 0


@dataclass
class TscnScene:
    path: str
    format_version: int = 3
    uid: Optional[str] = None
    ext_resources: list[TscnResource] = field(default_factory=list)
    sub_resources: list[TscnResource] = field(default_factory=list)
    nodes: list[TscnNode] = field(default_factory=list)
    connections: list[TscnConnection] = field(default_factory=list)
    root_node: Optional[TscnNode] = None


class TscnParser:
    """Parse Godot .tscn scene files."""
    
    # Patterns for parsing TSCN format
    HEADER_PATTERN = re.compile(
        r'\[gd_scene.*?format=(\d+).*?\]'
    )
    EXT_RESOURCE_PATTERN = re.compile(
        r'\[ext_resource\s+type="([^"]+)"\s+(?:uid="([^"]+)"\s+)?path="([^"]+)"\s+id="([^"]+)"\]'
    )
    SUB_RESOURCE_PATTERN = re.compile(
        r'\[sub_resource\s+type="([^"]+)"\s+id="([^"]+)"\]'
    )
    NODE_PATTERN = re.compile(
        r'\[node\s+name="([^"]+)"(?:\s+type="([^"]+)")?(?:\s+parent="([^"]+)")?(?:\s+instance=ExtResource\(\s*"([^"]+)"\s*\))?(?:\s+groups=\[([^\]]+)\])?\]'
    )
    CONNECTION_PATTERN = re.compile(
        r'\[connection\s+signal="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+method="([^"]+)"(?:\s+flags=(\d+))?\]'
    )
    PROPERTY_PATTERN = re.compile(
        r'^(\w+)\s*=\s*(.+)$', re.MULTILINE
    )
    
    def parse_file(self, path: str | Path) -> TscnScene:
        """Parse a .tscn file and return structured data."""
        path = Path(path)
        content = path.read_text(encoding='utf-8')
        return self.parse_content(content, str(path))
    
    def parse_content(self, content: str, path: str = "") -> TscnScene:
        """Parse TSCN content string."""
        scene = TscnScene(path=path)
        
        # Parse header
        header_match = self.HEADER_PATTERN.search(content)
        if header_match:
            scene.format_version = int(header_match.group(1))
        
        # Parse external resources
        for match in self.EXT_RESOURCE_PATTERN.finditer(content):
            resource = TscnResource(
                id=match.group(4),
                type=match.group(1),
                path=match.group(3)
            )
            if match.group(2):
                resource.properties['uid'] = match.group(2)
            scene.ext_resources.append(resource)
        
        # Split into sections
        sections = re.split(r'\n(?=\[)', content)
        
        current_sub_resource = None
        node_map: dict[str, TscnNode] = {}
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # Sub resources
            sub_match = self.SUB_RESOURCE_PATTERN.match(section)
            if sub_match:
                resource = TscnResource(
                    id=sub_match.group(2),
                    type=sub_match.group(1)
                )
                # Parse properties
                lines = section.split('\n')[1:]
                resource.properties = self._parse_properties(lines)
                scene.sub_resources.append(resource)
                continue
            
            # Nodes
            node_match = self.NODE_PATTERN.match(section)
            if node_match:
                node = TscnNode(
                    name=node_match.group(1),
                    type=node_match.group(2),
                    parent=node_match.group(3),
                    instance=node_match.group(4)
                )
                
                # Parse groups
                if node_match.group(5):
                    groups_str = node_match.group(5)
                    node.groups = [g.strip().strip('"') for g in groups_str.split(',')]
                
                # Parse properties
                lines = section.split('\n')[1:]
                node.properties = self._parse_properties(lines)
                
                scene.nodes.append(node)
                
                # Build parent-child relationships
                if node.parent is None:
                    scene.root_node = node
                    node_map["."] = node
                else:
                    parent_path = node.parent
                    if parent_path in node_map:
                        node_map[parent_path].children.append(node)
                    
                    # Calculate this node's path
                    if parent_path == ".":
                        node_path = node.name
                    else:
                        node_path = f"{parent_path}/{node.name}"
                    node_map[node_path] = node
                
                continue
            
            # Connections
            conn_match = self.CONNECTION_PATTERN.match(section)
            if conn_match:
                connection = TscnConnection(
                    signal=conn_match.group(1),
                    from_node=conn_match.group(2),
                    to_node=conn_match.group(3),
                    method=conn_match.group(4),
                    flags=int(conn_match.group(5)) if conn_match.group(5) else 0
                )
                scene.connections.append(connection)
        
        return scene
    
    def _parse_properties(self, lines: list[str]) -> dict:
        """Parse property lines into a dictionary."""
        properties = {}
        current_key = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a new property
            match = self.PROPERTY_PATTERN.match(line)
            if match:
                # Save previous property if exists
                if current_key:
                    properties[current_key] = '\n'.join(current_value)
                
                current_key = match.group(1)
                current_value = [match.group(2)]
            elif current_key:
                # Continuation of previous property
                current_value.append(line)
        
        # Save last property
        if current_key:
            properties[current_key] = '\n'.join(current_value)
        
        return properties
    
    def to_dict(self, scene: TscnScene) -> dict:
        """Convert TscnScene to dictionary for JSON serialization."""
        return {
            "path": scene.path,
            "format_version": scene.format_version,
            "external_resources": [
                {"id": r.id, "type": r.type, "path": r.path}
                for r in scene.ext_resources
            ],
            "sub_resources": [
                {"id": r.id, "type": r.type, "properties": r.properties}
                for r in scene.sub_resources
            ],
            "nodes": self._nodes_to_list(scene.nodes),
            "connections": [
                {
                    "signal": c.signal,
                    "from": c.from_node,
                    "to": c.to_node,
                    "method": c.method
                }
                for c in scene.connections
            ],
            "node_count": len(scene.nodes)
        }
    
    def _nodes_to_list(self, nodes: list[TscnNode]) -> list[dict]:
        """Convert nodes to list of dicts."""
        result = []
        for node in nodes:
            node_dict = {
                "name": node.name,
                "type": node.type,
                "parent": node.parent,
                "groups": node.groups,
                "properties": node.properties
            }
            if node.instance:
                node_dict["instance"] = node.instance
            result.append(node_dict)
        return result
    
    def get_node_tree(self, scene: TscnScene) -> dict:
        """Get hierarchical node tree starting from root."""
        if not scene.root_node:
            return {}
        return self._node_to_tree(scene.root_node)
    
    def _node_to_tree(self, node: TscnNode) -> dict:
        """Recursively convert node to tree dict."""
        return {
            "name": node.name,
            "type": node.type or "(instanced)",
            "groups": node.groups,
            "children": [self._node_to_tree(c) for c in node.children]
        }
