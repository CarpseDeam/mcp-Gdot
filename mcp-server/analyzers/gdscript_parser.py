"""
GDScript Static Analyzer
Parses .gd files to extract classes, functions, signals, exports, and dependencies.
Works completely offline - no Godot required.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GDSignal:
    name: str
    parameters: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class GDFunction:
    name: str
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None
    is_static: bool = False
    line: int = 0


@dataclass
class GDExport:
    name: str
    type: str
    default: Optional[str] = None
    hint: Optional[str] = None
    line: int = 0


@dataclass
class GDVariable:
    name: str
    type: Optional[str] = None
    default: Optional[str] = None
    line: int = 0


@dataclass 
class GDClass:
    name: Optional[str]  # class_name if defined
    extends: Optional[str]
    path: str
    signals: list[GDSignal] = field(default_factory=list)
    functions: list[GDFunction] = field(default_factory=list)
    exports: list[GDExport] = field(default_factory=list)
    variables: list[GDVariable] = field(default_factory=list)
    preloads: list[str] = field(default_factory=list)
    is_tool: bool = False
    

class GDScriptParser:
    """Parse GDScript files for static analysis."""
    
    # Regex patterns
    CLASS_NAME_PATTERN = re.compile(r'^class_name\s+(\w+)', re.MULTILINE)
    EXTENDS_PATTERN = re.compile(r'^extends\s+([^\s#]+)', re.MULTILINE)
    SIGNAL_PATTERN = re.compile(r'^signal\s+(\w+)(?:\((.*?)\))?', re.MULTILINE)
    FUNC_PATTERN = re.compile(
        r'^(static\s+)?func\s+(\w+)\s*\((.*?)\)(?:\s*->\s*(\w+))?',
        re.MULTILINE
    )
    EXPORT_PATTERN = re.compile(
        r'^@export(?:_(\w+)(?:\((.*?)\))?)?\s*var\s+(\w+)(?:\s*:\s*(\w+))?(?:\s*=\s*(.+?))?(?:\s*#|$)',
        re.MULTILINE
    )
    VAR_PATTERN = re.compile(
        r'^var\s+(\w+)(?:\s*:\s*(\w+))?(?:\s*=\s*(.+?))?(?:\s*#|$)',
        re.MULTILINE
    )
    PRELOAD_PATTERN = re.compile(r'preload\s*\(\s*["\'](.+?)["\']\s*\)')
    LOAD_PATTERN = re.compile(r'(?<!pre)load\s*\(\s*["\'](.+?)["\']\s*\)')
    TOOL_PATTERN = re.compile(r'^@tool', re.MULTILINE)
    
    def parse_file(self, path: str | Path) -> GDClass:
        """Parse a GDScript file and return structured data."""
        path = Path(path)
        content = path.read_text(encoding='utf-8')
        return self.parse_content(content, str(path))
    
    def parse_content(self, content: str, path: str = "") -> GDClass:
        """Parse GDScript content string."""
        lines = content.split('\n')
        
        gd_class = GDClass(
            name=None,
            extends=None,
            path=path
        )
        
        # Check for @tool
        gd_class.is_tool = bool(self.TOOL_PATTERN.search(content))
        
        # Extract class_name
        match = self.CLASS_NAME_PATTERN.search(content)
        if match:
            gd_class.name = match.group(1)
        
        # Extract extends
        match = self.EXTENDS_PATTERN.search(content)
        if match:
            gd_class.extends = match.group(1)
        
        # Extract signals
        for match in self.SIGNAL_PATTERN.finditer(content):
            signal = GDSignal(
                name=match.group(1),
                parameters=self._parse_params(match.group(2)) if match.group(2) else [],
                line=content[:match.start()].count('\n') + 1
            )
            gd_class.signals.append(signal)
        
        # Extract functions
        for match in self.FUNC_PATTERN.finditer(content):
            func = GDFunction(
                name=match.group(2),
                is_static=bool(match.group(1)),
                parameters=self._parse_params(match.group(3)),
                return_type=match.group(4),
                line=content[:match.start()].count('\n') + 1
            )
            gd_class.functions.append(func)
        
        # Extract exports
        for match in self.EXPORT_PATTERN.finditer(content):
            export = GDExport(
                name=match.group(3),
                type=match.group(4) or "Variant",
                hint=match.group(1),
                default=match.group(5),
                line=content[:match.start()].count('\n') + 1
            )
            gd_class.exports.append(export)
        
        # Extract variables (non-export)
        for match in self.VAR_PATTERN.finditer(content):
            # Skip if this line has @export
            line_start = content.rfind('\n', 0, match.start()) + 1
            line_content = content[line_start:match.start()]
            if '@export' in line_content:
                continue
                
            var = GDVariable(
                name=match.group(1),
                type=match.group(2),
                default=match.group(3),
                line=content[:match.start()].count('\n') + 1
            )
            gd_class.variables.append(var)
        
        # Extract preloads and loads
        for match in self.PRELOAD_PATTERN.finditer(content):
            gd_class.preloads.append(match.group(1))
        for match in self.LOAD_PATTERN.finditer(content):
            gd_class.preloads.append(match.group(1))
        
        return gd_class
    
    def _parse_params(self, params_str: str) -> list[str]:
        """Parse function/signal parameters."""
        if not params_str or not params_str.strip():
            return []
        return [p.strip() for p in params_str.split(',') if p.strip()]
    
    def to_dict(self, gd_class: GDClass) -> dict:
        """Convert GDClass to dictionary for JSON serialization."""
        return {
            "name": gd_class.name,
            "extends": gd_class.extends,
            "path": gd_class.path,
            "is_tool": gd_class.is_tool,
            "signals": [
                {"name": s.name, "parameters": s.parameters, "line": s.line}
                for s in gd_class.signals
            ],
            "functions": [
                {
                    "name": f.name,
                    "parameters": f.parameters,
                    "return_type": f.return_type,
                    "is_static": f.is_static,
                    "line": f.line
                }
                for f in gd_class.functions
            ],
            "exports": [
                {
                    "name": e.name,
                    "type": e.type,
                    "hint": e.hint,
                    "default": e.default,
                    "line": e.line
                }
                for e in gd_class.exports
            ],
            "variables": [
                {"name": v.name, "type": v.type, "default": v.default, "line": v.line}
                for v in gd_class.variables
            ],
            "dependencies": gd_class.preloads
        }
