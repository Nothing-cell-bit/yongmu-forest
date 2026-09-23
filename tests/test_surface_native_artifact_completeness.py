import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
sys.path.insert(0, str(BP))

from TwilightBossSlice import ruin_catalog_data  # noqa: E402


def coordinate(value):
    value = int(value)
    return "%s%02d" % ("m" if value < 0 else "p", abs(value))


class SurfaceNativeArtifactCompletenessTests(unittest.TestCase):
    def test_every_runtime_surface_tile_reference_exists_in_the_pack(self):
        catalog = json.loads(ruin_catalog_data.CATALOG_JSON)
        aliases = catalog.get("structureAliases", {})
        missing = []
        checked = 0

        for entry in catalog["structures"]:
            for variant in entry.get("variants", []):
                native = variant.get("surfaceNative")
                if not isinstance(native, dict):
                    continue
                prefix = native["prefix"]
                for alignment, bounds in native["centerAlignments"].items():
                    center_x, center_z = (
                        int(value) for value in alignment.split(",", 1)
                    )
                    for delta_x in range(int(bounds[0]), int(bounds[2]) + 1):
                        for delta_z in range(
                            int(bounds[1]), int(bounds[3]) + 1
                        ):
                            reference = (
                                "%s/mx%02d_mz%02d/x%s_z%s"
                                % (
                                    prefix,
                                    center_x,
                                    center_z,
                                    coordinate(delta_x),
                                    coordinate(delta_z),
                                )
                            )
                            reference = aliases.get(reference, reference)
                            path = BP / "structures" / (reference + ".mcstructure")
                            checked += 1
                            if not path.is_file() or path.stat().st_size <= 64:
                                missing.append(reference)

        self.assertGreater(checked, 1000)
        self.assertEqual(
            [],
            missing[:25],
            "%d of %d declared surface-native tiles are missing or empty"
            % (len(missing), checked),
        )


if __name__ == "__main__":
    unittest.main()
