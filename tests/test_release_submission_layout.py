"""Known upload-root failure must be rejected on actual archive members."""
import pathlib
import sys
import zipfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT.parent / "tools"))
import prepare_release_candidate as exporter
import release_audit


def rows():
    return [("behavior_pack/manifest.json", b"{}"),
            ("resource_pack/manifest.json", b"{}"),
            ("resource_pack/textures/items/example.png", b"texture")]


def test_component_root_allows_only_two_packs_with_real_texture_members():
    exporter.require_submission_layout(rows())
    with pytest.raises(ValueError):
        exporter.require_submission_layout(rows()[:2] + [("resource_pack/textures/", b"")])


@pytest.mark.parametrize("bad", ["root_notice", "wrapper", "missing_manifest"])
def test_final_zip_layout_rejects_known_upload_failures(tmp_path, bad):
    members = rows()
    if bad == "root_notice":
        members.append(("LICENSE_CODE.md", b"notice belongs in materials"))
    elif bad == "wrapper":
        members = [("outer/" + name, data) for name, data in members]
    else:
        members = members[1:]
    path = tmp_path / "candidate.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)
    with pytest.raises(ValueError):
        exporter.require_submission_layout(release_audit.members(path))


def test_notices_are_preserved_in_separate_materials(tmp_path):
    source, materials = tmp_path / "notices", tmp_path / "materials"
    source.mkdir()
    files = {"LICENSE_CODE.md": b"code", "THIRD_PARTY_NOTICES.md": b"attribution",
             "licenses/LGPL-2.1.txt": b"LGPL", "licenses/CC-BY-NC-SA-4.0.txt": b"assets"}
    for name, data in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    exporter.copy_notices(source, materials)
    assert {p.relative_to(materials).as_posix(): p.read_bytes()
            for p in materials.rglob("*") if p.is_file()} == files
    assert all((source / name).read_bytes() == data for name, data in files.items())
