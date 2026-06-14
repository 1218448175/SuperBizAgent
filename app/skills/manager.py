"""Skill 管理器 — Skill 生命周期管理（发现/加载/匹配/索引/激活/停用）"""

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from langchain_core.documents import Document
from loguru import logger

from app.config import config
from app.services.document_parser_service import (
    document_parser_service,
    SUPPORTED_EXTENSIONS,
)
from app.skills.base import SkillManifest, SkillContext
from app.skills.registry import skill_registry


class SkillManager:
    """Skill 生命周期管理器

    负责：
    - discover: 扫描目录发现所有 Skill
    - load: 加载 Skill 的 tools.py + prompt.md
    - match: 关键词匹配用户问题到最相关的 Skill
    - index: 将 Skill 知识文档索引到 Milvus
    - activate / deactivate: 运行时热激活/停用
    - reload: 从磁盘重新加载 Skill
    """

    def __init__(self, skills_dir: Optional[str] = None):
        """
        Args:
            skills_dir: Skill 存放目录，默认使用 config.skill_dir
        """
        self.skills_dir = Path(skills_dir or config.skill_dir).resolve()
        self._discovered = False
        logger.info(f"SkillManager 初始化，skills_dir={self.skills_dir}")

    # ── 发现 ────────────────────────────────────────────────────

    def discover_all(self) -> List[SkillManifest]:
        """扫描 skills_dir 下所有子目录，解析 skill.yaml 并注册"""
        if not self.skills_dir.exists():
            logger.warning(f"Skill 目录不存在: {self.skills_dir}")
            return []

        discovered: List[SkillManifest] = []
        for item in sorted(self.skills_dir.iterdir()):
            if not item.is_dir():
                continue
            yaml_path = item / "skill.yaml"
            if not yaml_path.exists():
                logger.debug(f"跳过非 Skill 目录: {item.name} (无 skill.yaml)")
                continue

            try:
                manifest = self._parse_manifest(yaml_path)
                skill_registry.register(manifest)
                discovered.append(manifest)
                logger.info(
                    f"发现 Skill: {manifest.name} ({manifest.display_name}) "
                    f"v{manifest.version} enabled={manifest.enabled}"
                )
            except Exception as e:
                logger.error(f"解析 Skill 失败: {yaml_path}, 错误: {e}")

        self._discovered = True
        logger.info(f"Skill 发现完成: 共 {len(discovered)} 个")
        return discovered

    def _parse_manifest(self, yaml_path: Path) -> SkillManifest:
        """解析单个 skill.yaml 文件"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"skill.yaml 内容必须是字典: {yaml_path}")
        if "name" not in data:
            raise ValueError(f"skill.yaml 缺少必填字段 'name': {yaml_path}")
        return SkillManifest(**data)

    # ── 加载 ────────────────────────────────────────────────────

    def load_skill(self, name: str) -> Optional[SkillContext]:
        """加载单个 Skill 的完整上下文（tools + prompt + docs）"""
        manifest = skill_registry.get_manifest(name)
        if manifest is None:
            logger.error(f"Skill '{name}' 未注册，请先 discover_all()")
            return None

        skill_dir = self.skills_dir / name

        # 1. 加载专用工具
        tools = self._load_tools(name, skill_dir)

        # 2. 加载领域提示词
        prompt = self._load_prompt(skill_dir)

        # 3. 统计知识文档
        doc_count = self._count_docs(skill_dir)

        context = SkillContext(
            manifest=manifest,
            prompt=prompt,
            tools=tools,
            doc_count=doc_count,
            indexed=False,  # 索引状态由调用方设置
        )
        logger.info(
            f"Skill 加载完成: {name}, tools={len(tools)}, "
            f"prompt_len={len(prompt)}, docs={doc_count}"
        )
        return context

    def _load_tools(self, name: str, skill_dir: Path) -> list:
        """从 tools.py 动态加载 @tool 函数"""
        tools_path = skill_dir / "tools.py"
        if not tools_path.exists():
            logger.debug(f"Skill '{name}' 无 tools.py")
            return []

        try:
            module_name = f"app.skills.builtin.{name}.tools"
            # 检查是否已导入
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(
                    module_name, str(tools_path)
                )
                if spec is None or spec.loader is None:
                    raise ImportError(f"无法加载模块: {tools_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            # 收集所有 @tool 装饰的函数（langchain_core.tools.BaseTool 实例）
            tools = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if hasattr(attr, "name") and hasattr(attr, "description"):
                    # 检查是否为 langchain BaseTool
                    from langchain_core.tools import BaseTool
                    if isinstance(attr, BaseTool):
                        tools.append(attr)
                        logger.debug(f"  加载工具: {attr.name}")

            return tools

        except Exception as e:
            logger.error(f"加载 Skill '{name}' 工具失败: {e}")
            return []

    def _load_prompt(self, skill_dir: Path) -> str:
        """读取 prompt.md"""
        prompt_path = skill_dir / "prompt.md"
        if not prompt_path.exists():
            logger.debug(f"Skill 目录无 prompt.md: {skill_dir}")
            return ""
        try:
            return prompt_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.error(f"读取 prompt.md 失败: {e}")
            return ""

    def _count_docs(self, skill_dir: Path) -> int:
        """统计 docs/ 目录下的知识文档数量"""
        docs_dir = skill_dir / "docs"
        if not docs_dir.exists():
            return 0
        return len(
            [f for f in docs_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
        )

    # ── 匹配 ────────────────────────────────────────────────────

    def match(self, query: str, top_k: Optional[int] = None) -> List[SkillManifest]:
        """基于关键词匹配，返回最相关的 Skill 列表

        匹配算法：
        1. 遍历所有启用的 Skill
        2. 对每个 Skill，检查 query 是否命中 keywords 或 trigger_patterns
        3. 按命中数降序排列
        4. 返回 Top-K

        Args:
            query: 用户输入文本
            top_k: 返回最多几个 Skill（默认使用 config.skill_match_top_k）

        Returns:
            按相关性降序排列的 SkillManifest 列表
        """
        if top_k is None:
            top_k = getattr(config, "skill_match_top_k", 2)

        query_lower = query.lower()
        scored: List[Tuple[SkillManifest, int]] = []

        for manifest in skill_registry.list_enabled():
            score = 0

            # 关键词匹配（每命中一个关键词 +1 分）
            for kw in manifest.keywords:
                if kw.lower() in query_lower:
                    score += 1

            # 正则匹配（每命中一个正则 +2 分，正则更精确）
            for pattern in manifest.trigger_patterns:
                try:
                    if re.search(pattern, query, re.IGNORECASE):
                        score += 2
                except re.error:
                    logger.warning(f"Skill '{manifest.name}' 正则表达式无效: {pattern}")

            if score > 0:
                scored.append((manifest, score))

        # 按分数降序排列
        scored.sort(key=lambda x: x[1], reverse=True)

        matched = [m for m, _ in scored[:top_k]]
        if matched:
            names = [m.name for m in matched]
            logger.info(f"Skill 匹配: query='{query[:60]}...' → {names}")
        else:
            logger.debug(f"Skill 匹配: query='{query[:60]}...' → 无匹配")

        return matched

    # ── 索引 ────────────────────────────────────────────────────

    def index_skill(self, name: str) -> Tuple[int, str]:
        """将 Skill 的知识文档索引到 Milvus

        Args:
            name: Skill 名称

        Returns:
            (已索引文档分片数, 错误信息)
        """
        from app.services.document_splitter_service import document_splitter_service
        from app.services.vector_store_manager import vector_store_manager

        manifest = skill_registry.get_manifest(name)
        if manifest is None:
            return 0, f"Skill '{name}' 未注册"

        docs_dir = self.skills_dir / name / "docs"
        if not docs_dir.exists():
            return 0, f"Skill '{name}' 无 docs/ 目录"

        total_indexed = 0
        errors: List[str] = []

        for doc_file in docs_dir.iterdir():
            if doc_file.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if doc_file.name.startswith("_"):
                continue  # 跳过以下划线开头的文件

            try:
                content = document_parser_service.parse(str(doc_file.resolve()))
                file_path = doc_file.resolve().as_posix()

                # 先删除旧数据
                vector_store_manager.delete_by_source(file_path)

                # 分割文档
                documents = document_splitter_service.split_document(
                    content, file_path
                )

                # 注入 Skill 元数据标签
                for doc in documents:
                    doc.metadata["skill"] = name
                    doc.metadata["skill_name"] = manifest.display_name

                # 写入向量库
                if documents:
                    vector_store_manager.add_documents(documents)
                    total_indexed += len(documents)
                    logger.info(
                        f"Skill '{name}' 文档索引完成: {doc_file.name} → {len(documents)} 分片"
                    )
            except Exception as e:
                err_msg = f"索引失败 {doc_file.name}: {e}"
                errors.append(err_msg)
                logger.error(err_msg)

        # 更新上下文索引状态
        ctx = skill_registry.get_active_context(name)
        if ctx:
            ctx.indexed = True
            ctx.doc_count = self._count_docs(self.skills_dir / name)

        error_str = "; ".join(errors) if errors else ""
        logger.info(f"Skill '{name}' 索引完成: 共 {total_indexed} 分片")
        return total_indexed, error_str

    def index_all_skills(self) -> Dict[str, Tuple[int, str]]:
        """索引所有已注册 Skill 的知识文档"""
        results = {}
        for m in skill_registry.list_manifests():
            if m.enabled:
                results[m.name] = self.index_skill(m.name)
        return results

    # ── 激活/停用（热加载）───────────────────────────────────────

    def activate(self, name: str) -> Tuple[bool, str]:
        """激活一个 Skill（加载 + 注入运行时）

        Args:
            name: Skill 名称

        Returns:
            (成功, 消息)
        """
        manifest = skill_registry.get_manifest(name)
        if manifest is None:
            return False, f"Skill '{name}' 未注册"

        if not manifest.enabled:
            return False, f"Skill '{name}' 已禁用，请先启用"

        # 检查依赖
        for dep in manifest.depends_on:
            if not skill_registry.is_active(dep):
                logger.warning(
                    f"Skill '{name}' 依赖 '{dep}'，但 '{dep}' 未激活"
                )

        # 加载 Skill 上下文
        context = self.load_skill(name)
        if context is None:
            return False, f"Skill '{name}' 加载失败"

        # 注册到运行时
        skill_registry.activate(context)

        # 如果配置了自动索引且未索引，则索引文档
        if getattr(config, "skill_auto_index", True) and not context.indexed:
            count, err = self.index_skill(name)
            context.indexed = True
            context.doc_count = self._count_docs(self.skills_dir / name)
            logger.info(f"Skill '{name}' 自动索引完成: {count} 分片")

        return True, f"Skill '{manifest.display_name}' 已激活 (tools={len(context.tools)}, docs={context.doc_count})"

    def deactivate(self, name: str) -> Tuple[bool, str]:
        """停用一个 Skill

        Args:
            name: Skill 名称

        Returns:
            (成功, 消息)
        """
        if not skill_registry.is_active(name):
            return False, f"Skill '{name}' 未激活"

        manifest = skill_registry.get_manifest(name)
        display = manifest.display_name if manifest else name
        skill_registry.deactivate(name)
        return True, f"Skill '{display}' 已停用"

    def activate_all(self) -> Dict[str, Tuple[bool, str]]:
        """激活所有启用的 Skill"""
        results = {}
        for m in skill_registry.list_enabled():
            results[m.name] = self.activate(m.name)
        return results

    def deactivate_all(self) -> Dict[str, Tuple[bool, str]]:
        """停用所有已激活的 Skill"""
        results = {}
        for name in list(skill_registry.active_skill_names):
            results[name] = self.deactivate(name)
        return results

    # ── 重载 ────────────────────────────────────────────────────

    def reload(self, name: str) -> Tuple[bool, str]:
        """从磁盘重新加载 Skill（先停用 → 重新解析 → 重新激活）

        Args:
            name: Skill 名称

        Returns:
            (成功, 消息)
        """
        was_active = skill_registry.is_active(name)

        # 停用
        if was_active:
            self.deactivate(name)

        # 重新解析 skill.yaml
        skill_dir = self.skills_dir / name
        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            return False, f"Skill '{name}' 的 skill.yaml 不存在"

        try:
            new_manifest = self._parse_manifest(yaml_path)
            skill_registry.unregister(name)
            skill_registry.register(new_manifest)
        except Exception as e:
            return False, f"重新解析 skill.yaml 失败: {e}"

        # 清除已导入的模块缓存（强制重新加载 tools.py）
        module_name = f"app.skills.builtin.{name}.tools"
        sys.modules.pop(module_name, None)

        # 如果之前是激活状态，重新激活
        if was_active:
            return self.activate(name)
        else:
            return True, f"Skill '{name}' 已重载（未激活）"

    def reload_all(self) -> Dict[str, Tuple[bool, str]]:
        """重载所有 Skill"""
        results = {}
        for m in skill_registry.list_manifests():
            results[m.name] = self.reload(m.name)
        return results

    # ── 便捷方法 ────────────────────────────────────────────────

    def get_active_context_for_agent(self) -> Tuple[list, str]:
        """获取当前激活 Skill 的工具列表和提示词（供 Agent 初始化使用）"""
        tools = skill_registry.get_active_tools()
        prompts = skill_registry.get_active_prompts()
        return tools, prompts

    def match_and_activate(self, query: str) -> List[SkillManifest]:
        """匹配并自动激活相关 Skill（一站式调用）"""
        matched = self.match(query)
        for m in matched:
            if not skill_registry.is_active(m.name):
                self.activate(m.name)
        # 停用不再匹配的 Skill（可选，由配置控制）
        return matched


# 全局单例
skill_manager = SkillManager()
