# -*- mode: python ; coding: utf-8 -*-
import platform

# 强制禁用签名配置
macos_codesign_settings = {
    'codesign_identity': None,
    'entitlements_file': None,
    'signing_requirements': ''
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
        # 加强排除可能触发签名的组件
        'electron',
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
        icon='static/source/icon.png',
        **macos_codesign_settings  # 应用签名禁用配置
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='server',
        **macos_codesign_settings  # 应用签名禁用配置
    )
    # 创建 .app bundle 时禁用签名
    app = BUNDLE(
        coll,
        name='server.app',
        icon='static/source/icon.png',
        bundle_identifier='com.superagent.party',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'True',
            'NSAppleScriptEnabled': 'NO'  # 禁用可能触发签名的功能
        },
        **macos_codesign_settings  # 关键：应用签名禁用配置到 BUNDLE
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
        icon='static/source/icon.png',
        **macos_codesign_settings
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='server',
        **macos_codesign_settings
    )
