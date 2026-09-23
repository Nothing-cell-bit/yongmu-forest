"""Run the explicit standard-library-only test suite for this code snapshot."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'TwilightBossSliceB'))

PUBLIC_TEST_MODULES = (
    'test_naga_logic',
    'test_hydra_logic',
    'test_lich_logic',
    'test_portal_logic',
    'test_scepter_logic',
    'test_maze_map_logic',
    'test_magic_map_logic',
    'test_public_block_logic',
    'test_hydra_route_progression_logic',
    'test_labyrinth_route_logic',
    'test_ur_ghast_route_logic',
)

def main():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(['tests.' + name for name in PUBLIC_TEST_MODULES])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    raise SystemExit(main())
