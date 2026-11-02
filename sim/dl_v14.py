"""从资料库下载 v1.4 交付包并解压到 _art_v1.4/。

用法：python sim/dl_v14.py [delivery|full|both]
必须用系统 Python 3.10（装了 pillow/numpy），且解压要用 zipfile（unzip 会乱中文名）。
"""
import io
import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = ('D:/workbuddy/resources/app.asar.unpacked/resources/plugins/'
         'workbuddy-builtin/skills/library')
NODES = {
    'delivery': 'gh5O6jZJq9sDv6tImq6oFJ',
    'full': 'ChNR2XbyPDAVL41OdLklDX',
}
PY = sys.executable


def _run(*args):
    out = subprocess.run([PY] + list(args), capture_output=True, cwd=ROOT)
    return out.stdout.decode('utf-8', 'replace')


def link(node_id):
    raw = _run(os.path.join(SKILL, 'drive', 'get_download_link.py'),
               '--node-id', node_id)
    for line in raw.splitlines():
        if line.startswith('KS_DRIVE_DOWNLOAD '):
            return json.loads(line[len('KS_DRIVE_DOWNLOAD '):])
    raise RuntimeError('拿不到下载链接：' + raw[:400])


def fetch(url, dest):
    from urllib.request import urlopen, Request
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req, timeout=180) as r, open(dest, 'wb') as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return os.path.getsize(dest)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'delivery'
    todo = [which] if which in NODES else list(NODES)
    for k in todo:
        info = link(NODES[k])
        name = info['file_name']
        zpath = os.path.join(ROOT, name)
        print('下载 %s (%.1f MB) ...' % (name, 0), flush=True)
        size = fetch(info['download_url'], zpath)
        print('  -> %d bytes (%.1f MB)' % (size, size / 1048576.0))
        zf = zipfile.ZipFile(zpath)
        bad = zf.testzip()
        print('  CRC testzip:', bad or 'OK', ' 条目数:', len(zf.namelist()))
        dest = os.path.join(ROOT, '_art_v1.4')
        # 只解 delivery 包的 Fox_Art 主体；full 包放到 _art_v1.4_full
        if k == 'full':
            dest = os.path.join(ROOT, '_art_v1.4_full')
        os.makedirs(dest, exist_ok=True)
        zf.extractall(dest)
        print('  解压 -> %s' % dest)
        # 列顶层
        top = sorted({n.split('/')[0] for n in zf.namelist()})
        print('  顶层:', top[:12])


if __name__ == '__main__':
    main()
