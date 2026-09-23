"""Package existing packs for import; no resource generation or deployment."""
from pathlib import Path
import argparse
import hashlib
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/yongmu-forest-0.12.0.mcaddon')
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / 'tools/check_runtime_packs.py')], check=True)
    target = args.output.resolve()
    if target.exists():
        parser.error('Output already exists; choose a new filename.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in ('TwilightBossSliceB', 'TwilightBossSliceR'):
            for path in sorted((ROOT / name).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'} and path.name != 'README.md':
                    archive.write(path, path.relative_to(ROOT).as_posix())
        for name in ('LICENSE', 'LICENSE_CODE.md', 'ASSET_LICENSE', 'ASSET_CREDITS.md',
                     'IMAGE_CREDITS.md', 'AUDIO_CREDITS.md', 'ASSET_MANIFEST.json',
                     'PACK_SNAPSHOT.json', 'licenses/LGPL-2.1.txt'):
            archive.write(ROOT / name, name)
        for path in sorted((ROOT / 'tools/audio_sources').rglob('*.source.json')):
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Archive integrity check failed')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix + '.sha256').write_text(digest + '  ' + target.name + '\n', encoding='ascii')
    print(str(target))
    print('SHA256: ' + digest)

if __name__ == '__main__':
    main()
