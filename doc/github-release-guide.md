# GitHub Release 自动发布指南

## GITHUB_TOKEN 说明

`GITHUB_TOKEN` 是GitHub Actions提供的自动令牌，它会在工作流运行时自动创建和配置。你不需要手动创建这个token，GitHub会自动处理。

### 权限配置

1. 在你的GitHub仓库中，进入 Settings -> Actions -> General
2. 滚动到 "Workflow permissions" 部分
3. 选择 "Read and write permissions"
4. 点击 "Save" 保存更改

这样配置后，GitHub Actions就有足够的权限来：
- 构建应用
- 创建releases
- 上传构建文件

## 发布新版本的步骤

1. 更新版本号
   ```bash
   # 修改 package.json 中的 version 字段
   ```

2. 提交更改
   ```bash
   git add package.json
   git commit -m "bump version to x.x.x"
   ```

3. 创建新的tag
   ```bash
   git tag vx.x.x
   ```

4. 推送到GitHub
   ```bash
   git push origin main --tags
   ```

5. 自动构建流程：
   - 推送tag后，本地不会生成任何文件
   - GitHub Actions会自动执行以下步骤：
     * 在Windows服务器上构建Windows版本（.exe）
     * 在macOS服务器上构建macOS版本（.dmg）
     * 在Linux服务器上构建Linux版本（.AppImage和.deb）
     * 创建新的GitHub Release
     * 将所有平台的安装包上传到Release页面
   - 构建完成后，可以在GitHub仓库的Releases页面下载安装包

## 本地构建说明

本项目提供了多个构建命令：

- `npm run build` - 同时构建所有平台版本
- `npm run build:win` - 仅构建Windows版本
- `npm run build:mac` - 仅构建macOS版本
- `npm run build:linux` - 仅构建Linux版本

注意：
- 在Windows系统上只能构建Windows版本
- 在macOS系统上只能构建macOS版本
- 在Linux系统上只能构建Linux版本
- GitHub Actions会自动在对应的系统上构建各自的版本

## 多平台支持

本项目支持在以下平台构建和发布：

### Windows
- 使用NSIS创建安装程序
- 生成文件：`Super Agent Party-Setup-{version}.exe`
- 支持自定义安装目录
- 创建桌面和开始菜单快捷方式

### macOS
- 生成DMG安装包
- 生成文件：`Super Agent Party-{version}-Mac.dmg`
- 提供标准的拖放安装界面
- 自动注册为生产力工具类应用

### Linux
- 提供两种安装包格式：
  * AppImage格式：`Super Agent Party-{version}-Linux.AppImage`
  * Debian包格式：`Super Agent Party-{version}-Linux.deb`
- AppImage无需安装，直接运行
- DEB包适用于基于Debian的发行版（如Ubuntu）

## 注意事项

- tag必须以`v`开头（例如：v0.1.2）
- 确保package.json中的version与tag版本号一致
- 首次发布时，确保已正确设置Workflow permissions
- 如果遇到权限相关错误，检查仓库的Actions权限设置
- 构建过程会同时在Windows、macOS和Linux环境中进行，可能需要等待较长时间
- Linux用户可以选择AppImage或DEB包进行安装


# 手动打包发布指南

本指南介绍如何在本地手动打包 Super Agent Party 应用。

## 环境准备

1. Node.js 环境 (v18+)
2. Python 环境 (v3.10+)
3. 安装依赖:
   ```bash
   # 安装 Node.js 依赖
   npm install

   # 安装 Python 依赖
   pip install -r requirements.txt
   pip install pyinstaller
   ```

## Python 后端打包

### Windows
```bash
# 执行打包
pyinstaller server.spec

# 创建发布目录
mkdir -p release/server

# 移动打包文件
mv dist/server/* release/server/
```

### macOS
```bash
# 执行打包
pyinstaller server.spec

# 创建发布目录
mkdir -p release/server

# 移动打包文件
mv "dist/server.app" release/server/
```

### Linux
```bash
# 执行打包
pyinstaller server.spec

# 创建发布目录
mkdir -p release/server

# 移动打包文件并设置权限
mv dist/server/* release/server/
chmod +x release/server/server
```

## Electron 应用打包

在完成 Python 后端打包后，执行 Electron 应用打包:

```bash
# 设置 GitHub Token (如果需要)
# export GH_TOKEN=your_token_here

# 执行打包
npm run build
```

打包完成后，可以在 release 目录下找到对应平台的安装包:
- Windows: `release/*.exe`
- macOS: `release/*.dmg`
- Linux: `release/*.AppImage` 和 `release/*.deb`

## 验证打包

1. 检查后端文件:
   - Windows: 确保 `release/server/server.exe` 存在
   - macOS: 确保 `release/server/server.app` 存在
   - Linux: 确保 `release/server/server` 存在且有执行权限

2. 检查前端安装包:
   - 确保安装包大小正常（通常在 100MB 以上）
   - 安装并运行应用，验证功能是否正常

## 常见问题

1. pyinstaller 打包失败
   - 检查 Python 依赖是否完整安装
   - 检查 server.spec 文件配置是否正确
   - 查看错误日志，确保所有必要的文件都被正确包含

2. Electron 打包失败
   - 检查 Node.js 依赖是否完整安装
   - 确保 GitHub Token 配置正确（如果需要）
   - 检查 package.json 中的构建配置

3. 运行时错误
   - 检查后端可执行文件权限
   - 验证文件路径是否正确
   - 查看应用日志获取详细错误信息

## 发布检查清单

- [ ] Python 后端打包成功
- [ ] 后端可执行文件位置正确
- [ ] Electron 应用打包成功
- [ ] 安装包可以正常安装
- [ ] 应用可以正常启动和运行
- [ ] 基本功能测试通过
