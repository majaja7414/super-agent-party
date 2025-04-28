# -*- mode: python ; coding: utf-8 -*-
import platform


a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/settings_template.json', 'config'),
        ('static', 'static'),
        ('node_modules', 'node_modules'),
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
    excludes=['Electron.app'],
    noarchive=False,
    optimize=0,
)
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
        console=False,  # macOS 使用 GUI 模式
        disable_windowed_traceback=False,
        argv_emulation=True,  # macOS 需要
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
    # 创建 .app bundle
    app = BUNDLE(
        coll,
        name='server.app',
        icon='static/source/icon.png',
        bundle_identifier='com.superagent.party',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'True',  # 后台运行
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
