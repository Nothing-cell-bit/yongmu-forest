"""Opt-in art variants; original source models and gameplay stay independent."""
import copy
import json
from pathlib import Path


def apply_entity_visual_overrides(path, document):
    path = Path(path)
    rp = next((parent for parent in path.parents if parent.name == "TwilightBossSliceR"), None)
    if rp is None:
        return document
    if not isinstance(document, dict) or not path.relative_to(rp).as_posix().startswith("entity/"):
        return document
    registry_path = rp.parent / "resource_art/entity_beautification/v1/manifest.json"
    if not registry_path.exists():
        return document
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not registry.get("enabled"):
        return document
    if registry.get("schema_version") != 1:
        raise ValueError("Unsupported entity art registry")
    description = document.get("minecraft:client_entity", {}).get("description", {})
    spec = registry.get("entities", {}).get(description.get("identifier"))
    if not spec or path.relative_to(rp).as_posix() != spec["client_entity"]:
        return document
    geometry_updates = spec.get("geometries", {"default":spec.get("geometry")})
    source_geometries = spec.get("source_geometries", {"default":spec.get("source_geometry")})
    for alias, target in geometry_updates.items():
        if description.get("geometry", {}).get(alias) not in (source_geometries[alias], target):
            raise ValueError("Entity source geometry changed; re-review the art variant")
    result = copy.deepcopy(document)
    output = result["minecraft:client_entity"]["description"]
    output["geometry"].update(geometry_updates)
    output["textures"].update(spec.get("textures", {"default":spec.get("texture")}))
    extra_animations = spec.get("animations", {})
    if extra_animations:
        output.setdefault("animations", {}).update(extra_animations)
    extra_animate = spec.get("animate", [])
    if extra_animate:
        animate = output.setdefault("scripts", {}).setdefault("animate", [])
        for alias in extra_animate:
            if alias not in animate:
                animate.append(alias)
    # Optional animation nodes must be omitted, not emitted empty: the live
    # NetEase decoder rejects {} / [] and then the static segment cannot load.
    if output.get("animations") == {}:
        output.pop("animations")
    scripts = output.get("scripts")
    if isinstance(scripts, dict):
        if scripts.get("animate") == []:
            scripts.pop("animate")
        if not scripts:
            output.pop("scripts")
    return result
