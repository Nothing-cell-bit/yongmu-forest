import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGED_SOUNDS = ROOT / "TwilightBossSliceR" / "sounds"
UPSTREAM_SOUNDS = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "sounds"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UpstreamSoundClearanceTests(unittest.TestCase):
    def test_pack_contains_no_byte_identical_upstream_ogg(self):
        if not UPSTREAM_SOUNDS.is_dir():
            self.skipTest("locked upstream extraction is unavailable")
        upstream_hashes = {
            sha256(path): path.relative_to(UPSTREAM_SOUNDS).as_posix()
            for path in UPSTREAM_SOUNDS.rglob("*.ogg")
        }
        matches = []
        for packaged in PACKAGED_SOUNDS.rglob("*.ogg"):
            upstream = upstream_hashes.get(sha256(packaged))
            if upstream:
                matches.append(
                    "%s == %s"
                    % (packaged.relative_to(PACKAGED_SOUNDS).as_posix(), upstream)
                )
        self.assertEqual(matches, [], "packaged upstream recordings: %s" % matches)

    def test_generators_cannot_reimport_upstream_sound_banks(self):
        hydra_generator = (ROOT / "tools" / "generate_hydra_sounds.py").read_text(
            encoding="utf-8"
        )
        hydra_builder = (ROOT / "tools" / "build_hydra_route_models.py").read_text(
            encoding="utf-8"
        )
        ruin_builder = (ROOT / "tools" / "build_ruin_dependencies.py").read_text(
            encoding="utf-8"
        )
        redcap_generator = (ROOT / "tools" / "generate_redcap_sounds.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("original-hydra-root", hydra_generator)
        self.assertNotIn("HYDRA_SOUNDS", hydra_builder)
        self.assertNotIn("copy_sound_bank", ruin_builder)
        self.assertNotIn("--source-root", redcap_generator)
        self.assertNotIn("--nailong-source", redcap_generator)


if __name__ == "__main__":
    unittest.main()
