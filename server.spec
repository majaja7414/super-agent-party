# -*- mode: python ; coding: utf-8 -*-
import platform

# 全平台禁用签名配置
universal_disable_sign = {
    'codesign_identity': None,
    'entitlements_file': None,
    'signing_requirements': '',
    'exclude_binaries': True  # 防止包含已签名二进制文件
}

a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/settings_template.json', 'config'),
        ('config/locales.json', 'config'),
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
    excludes=[
        'electron',  # 全局排除
        'electron-builder',
        'electron-updater',
        'node_modules/electron/**',
        'node_modules/electron-builder/**',
        'node_modules/electron-publish/**',
        'node_modules/electron-builder-squirrel-windows/**',
        'node_modules/electron-updater/**'
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# 全平台通用构建配置
base_exe_config = {
    'debug': False,
    'strip': False,
    'upx': True,
    'bootloader_ignore_signals': False,
    'disable_windowed_traceback': False,
    **universal_disable_sign  # 合并签名禁用配置
}

if platform.system() == 'Darwin':
    # macOS 特殊配置
    exe = EXE(
        pyz,
        a.scripts,
        [],
        name='server',
        console=False,
        argv_emulation=True,
        icon='static/source/icon.png',
        **base_exe_config
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name='server',
        upx_exclude=[],
        **universal_disable_sign
    )
    # macOS 专用 .app 配置
    app = BUNDLE(
        coll,
        name='server.app',
        icon='static/source/icon.png',
        bundle_identifier='com.superagent.party',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'True',
            'NSAppleScriptEnabled': 'NO'
        },
        **universal_disable_sign
    )
else:
    # Windows/Linux 配置
    exe = EXE(
        pyz,
        a.scripts,
        [],
        name='server',
        console=(platform.system() != 'Windows'),  # Windows 无弹窗
        icon='static/source/icon.png' if platform.system() == 'Windows' else None,
        **base_exe_config
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name='server',
        upx_exclude=[],
        **universal_disable_sign
    )
