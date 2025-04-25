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
