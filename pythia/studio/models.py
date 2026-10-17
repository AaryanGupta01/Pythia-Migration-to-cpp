"""Shared data model for PYTHIA Studio. Shapes are fixed by studio/CONTRACTS.md §2.

Everything here is plain dataclasses that round-trip through JSON. Private,
non-serialised analysis state lives in `FunctionRecord.private` (never dumped).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

JOURNEY_KEYS = ["original", "observed_types", "eligibility", "rewrites", "pysub",
                "tokens", "ast", "typed_ast", "pir", "cpp", "wrapper", "build",
                "replay", "benchmark", "splice", "status"]
STATUSES = ["pending", "verified", "guarded", "fixable", "not_eligible", "failed", "declined"]
STAGES = ["ingest", "scan", "trace", "rank", "fix", "compile", "verify",
          "benchmark", "splice", "export"]

SUMMARY_FIELDS = ["id", "file", "name", "qualname", "line", "end_line", "col", "status",
                  "eligibility", "reason", "decision", "share", "calls", "speedup",
                  "probe_speedup"]


def fid_hash(fid: str) -> str:
    return hashlib.sha1(fid.encode()).hexdigest()[:12]


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class FunctionRecord:
    id: str
    file: str
    name: str
    qualname: str = ""
    line: int = 0
    end_line: int = 0
    col: int = 0
    status: str = "pending"
    eligibility: str = "not_eligible"        # verifiable | fixable | not_eligible
    reason: Optional[str] = None
    decision: str = "pending"                # pending | accepted | rejected
    score: Dict[str, Any] = field(default_factory=lambda: {
        "total": 0.0, "trace_share": None, "static_heuristic": 0.0,
        "eligibility_factor": 0.0, "expected_benefit": 1.0,
        "boundary_penalty": 0.0, "basis": "static", "notes": []})
    share: Optional[float] = None
    calls: Optional[int] = None
    speedup: Optional[float] = None
    probe_speedup: Optional[float] = None
    metrics: Dict[str, Any] = field(default_factory=lambda: {
        "size_lines": 0, "loop_depth": 0, "arith_density": 0.0,
        "calls": [], "imports": [], "uses_globals": []})
    trace: Optional[Dict[str, Any]] = None
    sources: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "original": "", "annotated": None, "pysub": None, "cpp": None, "wrapper_cpp": None})
    line_map_ok: bool = True
    cpp_line_map: Dict[str, List[int]] = field(default_factory=dict)
    rewrites: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    fidelity: List[Dict[str, Any]] = field(default_factory=list)
    build: Optional[Dict[str, Any]] = None
    replay: Optional[Dict[str, Any]] = None
    bench: Optional[Dict[str, Any]] = None
    splice: Optional[Dict[str, Any]] = None
    journey: List[Dict[str, Any]] = field(default_factory=list)
    # not serialised: analysis scratch (ast nodes, extraction context, ...)
    private: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "private"}
        d["score"] = dict(self.score)
        return d

    def to_summary(self) -> Dict[str, Any]:
        d = {k: getattr(self, k) for k in SUMMARY_FIELDS}
        d["score"] = {"total": self.score.get("total", 0.0)}
        d["loop_depth"] = self.metrics.get("loop_depth", 0)
        d["size_lines"] = self.metrics.get("size_lines", 0)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "FunctionRecord":
        names = FunctionRecord.__dataclass_fields__.keys()
        return FunctionRecord(**{k: v for k, v in d.items() if k in names and k != "private"})


@dataclass
class Workspace:
    ws_id: str
    name: str
    root: Path                 # $PYTHIA_HOME/workspaces/<ws_id>
    original: Path             # pristine copy
    work: Path                 # accelerated copy (splice target)
    py_files: List[str] = field(default_factory=list)      # relpaths, forward slashes
    skipped: List[Dict[str, str]] = field(default_factory=list)
    input_kind: str = ""
    origin: str = ""           # folder path / git url / filename

    def to_dict(self) -> Dict[str, Any]:
        return {"ws_id": self.ws_id, "name": self.name, "root": str(self.root),
                "py_files": self.py_files, "skipped": self.skipped,
                "input_kind": self.input_kind, "origin": self.origin}
