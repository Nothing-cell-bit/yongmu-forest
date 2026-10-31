"""NetEase dimension render settings, separate from vanilla biome registration.

NetEase's documented renderer consumes RP/biomes_client.json. Modern client
biome definitions validate against the vanilla registry before NetEase creates
dimension-prefixed biomes, producing startup errors. Retain the complete art
profiles outside the runtime pack and emit only documented legacy fields.
"""

import json
from pathlib import Path


def profile_directory(root):
    return Path(root) / "resource_art" / "biome_profiles"


def legacy_document(root):
    root = Path(root)
    fogs = {}
    for path in (root / "TwilightBossSliceR" / "fogs").glob("*.json"):
        fog = json.loads(path.read_text(encoding="utf-8"))["minecraft:fog_settings"]
        fogs[fog["description"]["identifier"]] = fog
    biomes = {}
    for path in sorted(profile_directory(root).glob("*.client_biome.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))["minecraft:client_biome"]
        identifier = profile["description"]["identifier"]
        if not identifier.startswith("dm33027004_") or identifier in biomes:
            raise ValueError("Invalid or duplicate dimension render profile: " + identifier)
        components = profile["components"]
        fog_id = components["minecraft:fog_appearance"]["fog_identifier"]
        fog = fogs[fog_id]
        biomes[identifier] = {
            "water_surface_color": components["minecraft:water_appearance"]["surface_color"],
            "fog_identifier": fog_id,
            "fog_color": fog["distance"]["air"]["fog_color"],
            "water_fog_color": fog["distance"]["water"]["fog_color"],
            "water_fog_distance": fog["distance"]["water"]["fog_end"],
            "inherit_from_prior_fog": False,
        }
    if not biomes:
        raise ValueError("No dimension render profiles")
    return {"biomes": biomes}


def write_legacy_registry(root):
    path = Path(root) / "TwilightBossSliceR" / "biomes_client.json"
    path.write_text(json.dumps(legacy_document(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_profile(root, document):
    root = Path(root)
    identifier = document["minecraft:client_biome"]["description"]["identifier"]
    if not identifier.startswith("dm33027004_") or "/" in identifier or "\\" in identifier:
        raise ValueError("Invalid dimension profile identifier")
    path = profile_directory(root) / (identifier + ".client_biome.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
