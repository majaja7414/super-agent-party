# -*- mode: python ; coding: utf-8 -*-
import platform
from PyInstaller.utils.hooks import Tree
a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/settings_template.json', 'config'),
        ('static', 'static'),
        Tree('node_modules', prefix='node_modules', excludes=['**/Electron.app/**']),
        ('tiktoken_cache', 'tiktoken_cache')
    ],
    hiddenimports=[
        'pydantic.deprecated.decorator',
        'tiktoken_ext',
        'tiktoken_ext.openai_public'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# 强制过滤Electron二进制
a.binaries = [x for x in a.binaries if 'Electron.app' not in x[0]]
pyz = PYZ(a.pure)
if platform.system() == 'Darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='server',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='static/source/icon.png',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='server',
    )
    app = BUNDLE(
        coll,
        name='server.app',
        icon='static/source/icon.png',
        bundle_identifier='com.superagent.party',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'True',
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='server',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='static/source/icon.png',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='server',
    )
