import importlib.util
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_texture_layout', ROOT/'tools/release_texture_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


def fixture_rows():
    return [
        ('TwilightBossSliceR/textures/tf_beautified/', b''),
        ('TwilightBossSliceR/textures/tf_beautified/blocks/dirt.png', b'unchanged-png-payload'),
        ('TwilightBossSliceR/textures/tf_beautified/items/apple.png', b'item-payload'),
        ('TwilightBossSliceR/textures/tf_beautified/remaining/ui/tf_slice/magic_map_player/north.png', b'marker-payload'),
        ('TwilightBossSliceR/textures/terrain_texture.json', b'{"texture_data":{"dirt":{"textures":"textures/tf_beautified/blocks/dirt"}}}'),
        ('TwilightBossSliceB/TwilightBossSlice/map.py', b'icon = "textures/tf_beautified/remaining/ui/tf_slice/magic_map_player/" + direction\n'),
        ('TwilightBossSliceB/structures/keep.mcstructure', b'binary-structure'),
        ('LICENSE.txt', b'license'),
        ('TwilightBossSliceB/entities/', b''),
    ]


def test_real_cli_preserves_input_and_updates_json_and_dynamic_python(tmp_path):
    source, output, report = (tmp_path / p for p in ['old.zip', 'new.zip', 'report.json'])
    with zipfile.ZipFile(source, 'w') as z:
        for name, data in fixture_rows():
            z.writestr(name, data)
    original = source.read_bytes()
    command = [sys.executable, str(ROOT/'tools/release_texture_layout.py'),
               '--archive', str(source), '--output', str(output), '--report', str(report)]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert source.read_bytes() == original
    with zipfile.ZipFile(output) as z:
        assert z.read('TwilightBossSliceR/textures/blocks/tf_beautified/dirt.png') == b'unchanged-png-payload'
        assert z.read('TwilightBossSliceR/textures/items/tf_beautified/apple.png') == b'item-payload'
        assert json.loads(z.read('TwilightBossSliceR/textures/terrain_texture.json'))['texture_data']['dirt']['textures'] == 'textures/blocks/tf_beautified/dirt'
        assert z.read('TwilightBossSliceB/TwilightBossSlice/map.py') == b'icon = "textures/ui/tf_beautified/tf_slice/magic_map_player/" + direction\n'
        assert z.read('TwilightBossSliceB/structures/keep.mcstructure') == b'binary-structure'
        assert z.read('LICENSE.txt') == b'license'
        assert 'TwilightBossSliceB/entities/' in z.namelist()
        assert all('textures/tf_beautified/' not in n for n in z.namelist())
    assert json.loads(report.read_text())['moved_png_count'] == 3
    output_before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == output_before


def test_refuses_destination_collision_unknown_routes_and_missing_reference():
    with pytest.raises(ValueError, match='collision'):
        layout.transform(fixture_rows() + [('TwilightBossSliceR/textures/blocks/tf_beautified/dirt.png', b'other')], 'TwilightBossSliceR')
    with pytest.raises(ValueError, match='Unmapped'):
        layout.transform(fixture_rows() + [('TwilightBossSliceR/textures/tf_beautified/unknown/foo.png', b'foo')], 'TwilightBossSliceR')
    with pytest.raises(ValueError, match='Missing relocated'):
        layout.transform(fixture_rows() + [('TwilightBossSliceR/ui/missing.json', b'{"texture":"textures/tf_beautified/items/missing"}')], 'TwilightBossSliceR')


def test_verifier_rejects_old_layout_missing_references_and_changed_pixels():
    before = fixture_rows()
    after, report = layout.transform(before, 'TwilightBossSliceR')
    with pytest.raises(ValueError):
        layout.verify(before, before, report, 'TwilightBossSliceR')
    mutated = [(n, b'changed' if n.endswith('dirt.png') else d) for n, d in after]
    with pytest.raises(ValueError, match='Unexpected file change'):
        layout.verify(before, mutated, report, 'TwilightBossSliceR')
    mutated = [(n, b'{"texture":"textures/tf_beautified/blocks/dirt"}' if n.endswith('terrain_texture.json') else d) for n, d in after]
    with pytest.raises(ValueError):
        layout.verify(before, mutated, report, 'TwilightBossSliceR')


def test_staging_is_idempotent_and_keeps_required_empty_dirs(tmp_path):
    for name, data in fixture_rows():
        path = tmp_path / name
        if name.endswith('/'):
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    report = layout.apply_staging(tmp_path, 'TwilightBossSliceR')
    assert report['moved_png_count'] == 3
    assert not (tmp_path/'TwilightBossSliceR/textures/tf_beautified').exists()
    assert (tmp_path/'TwilightBossSliceB/entities').is_dir()
    second = layout.apply_staging(tmp_path, 'TwilightBossSliceR')
    assert second['moved_png_count'] == 0
    assert second['edited_reference_file_count'] == 0


def test_release_builder_cli_applies_layout_before_final_archive():
    # The builder intentionally permits staging only inside the workspace.
    with tempfile.TemporaryDirectory(prefix='texture-layout-test-', dir=ROOT/'.task-work') as directory:
        task = Path(directory)
        source = task/'source'
        for name, data in fixture_rows():
            path = source/name
            if name.endswith('/'):
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        for pack in ['TwilightBossSliceB', 'TwilightBossSliceR']:
            (source/pack/'manifest.json').write_text('{"format_version":2}', encoding='utf-8')
        # The production exporter now validates the complete mining contract.
        # Supply real definitions, never bypass the new guard for this fixture.
        for folder in ('netease_blocks', 'items'):
            shutil.copytree(ROOT/'TwilightBossSliceB'/folder, source/'TwilightBossSliceB'/folder, dirs_exist_ok=True)
        for relative in ('loot_tables/blocks/tf_slice/no_mining_drop.json',
                         'TwilightBossSlice/mining_tool_rules.py'):
            target = source/'TwilightBossSliceB'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/'TwilightBossSliceB'/relative, target)
        output = task/'candidate.zip'
        result = subprocess.run([sys.executable, str(ROOT/'tools/prepare_release_candidate.py'),
                                 '--source-root', str(source), '--staging', str(task/'staging'),
                                 '--archive', str(output), '--report', str(task/'report.json')],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        with zipfile.ZipFile(output) as z:
            assert 'resource_pack/textures/blocks/tf_beautified/dirt.png' in z.namelist()
            assert not any('textures/tf_beautified/' in n for n in z.namelist())
            assert b'textures/ui/tf_beautified/' in z.read('behavior_pack/TwilightBossSlice/map.py')
        assert (source/'TwilightBossSliceR/textures/tf_beautified/blocks/dirt.png').exists()
