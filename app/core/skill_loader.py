"""
Input: skill_id / stock_code / 可选 data/skills 片段
Output: system_hint 字符串 + skill meta（stub，非数据 adapter）
Pos: app/core/skill_loader.py — Sprint4+ Skills 最小 stub

[NEW-FILE:#20260724-S4B]
- 优先读 data/skills/{id}.md|.txt|.json（若目录存在）
- 否则从 agent_reflections / agent_strategies 拼一段提示（禁止替代 adapters）

一旦我被修改，请更新我的头部注释，以及所属文件夹的 md。
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 仓库根：app/core → parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / "data" / "skills"
_REFLECTIONS_DIR = _REPO_ROOT / "data" / "agent_reflections"
_STRATEGIES_DIR = _REPO_ROOT / "data" / "agent_strategies"

# 内置只读 skill stub（不触网、不拉行情）
_BUILTIN_SKILLS: Dict[str, Dict[str, Any]] = {
    "risk_checklist": {
        "id": "risk_checklist",
        "title": "高风险决策自检清单",
        "source": "builtin",
        "system_hint": (
            "【Skill: risk_checklist】回答高风险投资建议前自检："
            "1) 是否区分提案与已成交；2) 置信度与风险等级是否一致；"
            "3) 是否引用真实数据源而非臆造价格；4) 写仓须走 propose→approve→apply，"
            "禁止声称已下单；5) 缺数据时用「暂无/加载中」而非假值。"
        ),
    },
    "portfolio_readonly": {
        "id": "portfolio_readonly",
        "title": "持仓只读约束",
        "source": "builtin",
        "system_hint": (
            "【Skill: portfolio_readonly】持仓相关工具为只读快照。"
            "不得假装 mutate 用户组合；拟写须 propose_portfolio_write，"
            "经 approval_id（HITL 可见）后再 apply_portfolio_proposal（local_mark_only）。"
        ),
    },
    "analysis_plan": {
        "id": "analysis_plan",
        "title": "多步分析计划",
        "source": "builtin",
        "system_hint": (
            "【Skill: analysis_plan】复杂分析可先 create_analysis_plan 建串行/DAG 步骤，"
            "用 get_plan_status 查询；计划本身不执行抓数，步骤完成由宿主推进。"
        ),
    },
}


class SkillLoader:
    """Skills stub 加载器（RLock；进程内缓存 file mtime）。"""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._skills_dir = Path(skills_dir) if skills_dir else _SKILLS_DIR
        self._file_cache: Dict[str, Dict[str, Any]] = {}

    def list_skills(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for sid, meta in _BUILTIN_SKILLS.items():
            items.append(
                {
                    "id": sid,
                    "title": meta.get("title"),
                    "source": "builtin",
                }
            )
        if self._skills_dir.is_dir():
            for p in sorted(self._skills_dir.iterdir()):
                if p.suffix.lower() not in (".md", ".txt", ".json"):
                    continue
                sid = p.stem
                if any(x["id"] == sid for x in items):
                    continue
                items.append(
                    {
                        "id": sid,
                        "title": sid,
                        "source": "data/skills",
                        "path": str(p),
                    }
                )
        # 动态 reflection 技能入口（按 code 加载）
        items.append(
            {
                "id": "reflection_hint",
                "title": "标的反思/策略片段",
                "source": "agent_reflections|agent_strategies",
            }
        )
        return items

    def _load_file_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        if not self._skills_dir.is_dir():
            return None
        for suffix in (".md", ".txt", ".json"):
            path = self._skills_dir / f"{skill_id}{suffix}"
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                logger.debug("skill file read fail %s: %s", path, e)
                return None
            if suffix == ".json":
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {"system_hint": text[:2000]}
                hint = (
                    data.get("system_hint")
                    or data.get("hint")
                    or data.get("content")
                    or text
                )
                return {
                    "id": skill_id,
                    "title": data.get("title") or skill_id,
                    "source": f"data/skills/{path.name}",
                    "system_hint": str(hint)[:4000],
                }
            return {
                "id": skill_id,
                "title": skill_id,
                "source": f"data/skills/{path.name}",
                "system_hint": text.strip()[:4000],
            }
        return None

    def _reflection_hint(self, stock_code: str, max_items: int = 2) -> str:
        code = (stock_code or "").strip()
        if not code:
            return ""
        parts: List[str] = []
        # strategy
        sp = _STRATEGIES_DIR / f"{code}_strategy.json"
        if sp.is_file():
            try:
                raw = json.loads(sp.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    summary = (
                        raw.get("summary")
                        or raw.get("strategy_summary")
                        or raw.get("notes")
                        or ""
                    )
                    if not summary:
                        # 取若干关键字段拼短摘要
                        keys = [
                            k
                            for k in (
                                "focus",
                                "risk_preference",
                                "style",
                                "updated_at",
                            )
                            if k in raw
                        ]
                        summary = json.dumps(
                            {k: raw.get(k) for k in keys[:4]},
                            ensure_ascii=False,
                        )
                    if summary:
                        parts.append(f"策略片段({code}): {str(summary)[:600]}")
            except Exception as e:
                logger.debug("strategy load fail %s: %s", code, e)
        # reflections
        rp = _REFLECTIONS_DIR / f"{code}_reflections.json"
        if rp.is_file():
            try:
                raw = json.loads(rp.read_text(encoding="utf-8"))
                records = raw if isinstance(raw, list) else raw.get("reflections") or []
                if isinstance(records, list):
                    for rec in records[-max_items:]:
                        if not isinstance(rec, dict):
                            continue
                        ref = rec.get("reflection") or rec
                        if isinstance(ref, dict):
                            cons = ref.get("consistency") or ""
                            gaps = ref.get("information_gaps") or []
                            line = cons
                            if gaps and isinstance(gaps, list):
                                line = (line + " | gaps: " + "; ".join(str(g) for g in gaps[:2])).strip(" |")
                            if line:
                                parts.append(f"反思({code}): {str(line)[:500]}")
                        elif isinstance(ref, str) and ref.strip():
                            parts.append(f"反思({code}): {ref.strip()[:500]}")
            except Exception as e:
                logger.debug("reflection load fail %s: %s", code, e)
        if not parts:
            return (
                f"【Skill: reflection_hint】标的 {code} 暂无本地反思/策略片段；"
                "勿编造历史决策，缺则说明「暂无」。"
            )
        body = "\n".join(parts)
        return (
            f"【Skill: reflection_hint】以下为本地历史反思/策略摘录（非实时行情，"
            f"不可替代 adapters 取数）:\n{body}"
        )[:4000]

    def load_skill(
        self,
        skill_id: str,
        *,
        stock_code: str = "",
    ) -> Dict[str, Any]:
        sid = (skill_id or "").strip()
        if not sid:
            return {
                "success": False,
                "error_code": "INVALID_INPUT",
                "message": "skill_id 必填",
                "skill": None,
                "system_hint": "",
            }
        with self._lock:
            # 1) data/skills file
            file_skill = self._load_file_skill(sid)
            if file_skill:
                return {
                    "success": True,
                    "error_code": None,
                    "message": "ok",
                    "skill": file_skill,
                    "system_hint": file_skill["system_hint"],
                }
            # 2) builtin
            if sid in _BUILTIN_SKILLS:
                meta = dict(_BUILTIN_SKILLS[sid])
                return {
                    "success": True,
                    "error_code": None,
                    "message": "ok",
                    "skill": meta,
                    "system_hint": meta["system_hint"],
                }
            # 3) reflection_hint
            if sid in ("reflection_hint", "reflection", f"reflection_{stock_code}"):
                hint = self._reflection_hint(stock_code)
                skill = {
                    "id": "reflection_hint",
                    "title": "标的反思/策略片段",
                    "source": "agent_reflections|agent_strategies",
                    "stock_code": (stock_code or "").strip(),
                    "system_hint": hint,
                }
                return {
                    "success": True,
                    "error_code": None,
                    "message": "ok",
                    "skill": skill,
                    "system_hint": hint,
                }
            return {
                "success": False,
                "error_code": "SKILL_NOT_FOUND",
                "message": f"未知 skill_id: {sid}",
                "skill": None,
                "system_hint": "",
            }


_loader: Optional[SkillLoader] = None
_loader_lock = threading.Lock()


def get_skill_loader() -> SkillLoader:
    global _loader
    with _loader_lock:
        if _loader is None:
            override = os.getenv("SKILLS_DIR", "").strip()
            _loader = SkillLoader(Path(override) if override else None)
        return _loader


def load_skill_system_hint(skill_id: str, stock_code: str = "") -> str:
    """便捷：只返回 system_hint 字符串（失败空串）。"""
    res = get_skill_loader().load_skill(skill_id, stock_code=stock_code)
    return res.get("system_hint") or ""
