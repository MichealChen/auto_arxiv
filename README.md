# auto_arxiv

`auto_arxiv` 是一个 Windows 桌面应用，用来按你的研究兴趣自动推荐 arXiv 论文。普通用户只需要下载压缩包、解压、双击运行，不需要安装 Python，也不需要打开浏览器。

## 安装教程

`auto_arxiv` 目前提供 Windows x64 版本。请按下面步骤安装。

### 1. 进入下载页面

打开项目的 Releases 页面：

```text
https://github.com/MichealChen/auto_arxiv/releases
```

也可以直接下载最新版：

```text
https://github.com/MichealChen/auto_arxiv/releases/latest/download/auto_arxiv-windows-x64.zip
```

### 2. 下载 x64 压缩包

在 Releases 页面中，找到最新版本，例如 `v0.1.0`。

在页面下方的 `Assets` 区域，点击下载：

```text
auto_arxiv-windows-x64.zip
```

如果浏览器提示“此文件不常下载”，请选择保留。这个提示通常是因为软件还没有代码签名证书。

### 3. 解压软件

下载完成后，右键 `auto_arxiv-windows-x64.zip`，选择“全部解压”。

建议解压到一个固定目录，例如：

```text
D:\Apps\auto_arxiv\
```

解压后，文件夹里应该能看到：

```text
auto_arxiv.exe
_internal\
```

注意：不要只移动或复制单独的 `auto_arxiv.exe`。`_internal` 文件夹必须和 `auto_arxiv.exe` 放在同一个目录，否则软件无法启动。

### 4. 启动软件

双击：

```text
auto_arxiv.exe
```

第一次启动时，Windows 可能提示“Windows 已保护你的电脑”或“未知发布者”。

如果你确认软件来自本项目 Release 页面，可以点击：

```text
更多信息 -> 仍要运行
```

软件启动后会自动在同目录创建配置和数据文件，不需要手动创建。

## 使用教程

### 1. 第一次配置账户

打开软件后，点击左下角的“账户设置”。

建议按下面顺序填写：

- `Profile 名称`：你的账户名称，例如 `My Research Radar`。
- `arXiv 分类`：从下拉框中选择分类后点击“添加”，例如 `cs.LG`、`cs.CL`、`quant-ph`。
- `兴趣关键词`：输入你关心的研究关键词，每次输入一个，点击“添加”。
- `排除关键词`：输入不想看的内容，例如 `tutorial`、`workshop`、`position paper`。
- `关注作者`：输入你特别关注的作者姓名，例如 `Jens Eisert`。

保存后，账户设置窗口会自动关闭。

### 2. 生成推荐

主界面提供三种生成方式：

- “生成今日推荐”：生成今天的论文推荐。
- “生成该日期推荐”：点击日期框选择某一天，再生成该日期推荐。
- “生成范围推荐”：选择开始日期和结束日期，批量生成这一段时间内每天的推荐。

日期推荐会使用截至该日的滚动窗口，不会因为周末、假期或 arXiv 更新延迟就轻易出现“抓取 0”。

### 3. 阅读论文

生成后，左侧是推荐列表，右侧是论文详情。

你可以：

- 点击论文查看标题、作者、分类、推荐理由和摘要。
- 点击“下载 PDF”保存论文 PDF。
- 点击“复制 arXiv 链接”复制论文页面地址。
- 点击“加入/移出待读列表”收藏值得之后阅读的论文。
- 点击“标记已读/未读”管理阅读状态。

### 4. 待读列表和笔记

进入“待读列表”页后，可以查看已收藏论文。点击一篇论文后，可以在右侧写阅读笔记，然后点击“保存笔记”。

不同账户的待读列表和笔记彼此独立。

### 5. 关注作者规则

关注作者是额外推荐通道：

- 程序会单独查询关注作者的论文。
- 如果作者命中、分类命中，并且至少一个兴趣关键词命中，该论文会直接进入推荐列表。
- 关注作者论文不占用普通推荐数量 `limit`。
- 关注作者论文不受普通评分阈值 `min_score` 影响。

### 6. 数据保存在哪里

软件会在 `auto_arxiv.exe` 同目录自动创建这些文件夹和文件：

```text
config.toml          当前运行配置
profiles.json        多账户/Profile 配置
data/                推荐数据、历史记录、待读状态、笔记
downloads/           下载的 PDF
recommendations/     Markdown 推荐报告
```

如果你要备份自己的使用数据，备份这些文件即可。

## 常见问题

### Windows 提示“未知发布者”怎么办？

当前应用还没有代码签名证书。若你确认压缩包来自本项目 GitHub Release，可以点击“更多信息”然后选择“仍要运行”。

### 为什么推荐结果很少？

可以在“账户设置”里尝试：

- 增加 `max_results`，例如从 `100` 调到 `300`。
- 降低 `min_score`，例如从 `2.0` 调到 `1.0`。
- 增加或放宽兴趣关键词。
- 检查 arXiv 分类是否选得过窄。

### 下载 PDF 失败怎么办？

通常是网络或 arXiv 短时间不可用。稍后重试即可。

### 可以有多个研究方向吗？

可以。点击左下角“新建账户”，为不同方向建立不同 Profile。每个 Profile 有独立配置、历史、待读列表和笔记。

## 本地开发教程

下面内容只面向开发者。普通用户不需要执行这些命令。

### 1. 克隆项目

```powershell
git clone https://github.com/MichealChen/auto_arxiv.git
cd auto_arxiv
```

### 2. 创建开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e .[dev]
```

### 3. 准备配置

```powershell
Copy-Item config.example.toml config.toml
```

然后按自己的研究方向编辑 `config.toml`。

### 4. 命令行生成推荐

```powershell
.\.venv\Scripts\python -m auto_arxiv recommend --config config.toml
```

### 5. 启动本地 Web 调试页面

```powershell
.\.venv\Scripts\python -m auto_arxiv serve --config config.toml
```

浏览器打开：

```text
http://127.0.0.1:8765
```

### 6. 启动桌面应用开发版

```powershell
.\.venv\Scripts\python -m auto_arxiv.desktop
```

### 7. 运行测试

```powershell
.\.venv\Scripts\python -m pytest
```

### 8. 构建 Windows 应用

```powershell
.\scripts\build_exe.ps1
```

构建完成后会生成：

```text
dist\auto_arxiv\auto_arxiv.exe
```

分发时需要打包整个文件夹：

```text
dist\auto_arxiv\
```

### 9. 生成 Release 压缩包

```powershell
.\scripts\package_release.ps1
```

生成结果：

```text
release\auto_arxiv-windows-x64.zip
```

这个 zip 就是上传到 GitHub Release 的文件。

## GitHub 发布流程

### 第一次上传项目

```powershell
git init
git add README.md 开发文档.md pyproject.toml config.example.toml auto_arxiv_desktop.spec scripts packaging public src tests .github .gitignore
git commit -m "Initial release"
git branch -M main
git remote add origin https://github.com/MichealChen/auto_arxiv.git
git push -u origin main
```

不要上传这些本地运行数据：

```text
config.toml
profiles.json
data/
downloads/
recommendations/
dist/
release/
.venv/
```

这些已经写入 `.gitignore`。

### 发布新版

创建并推送 tag：

```powershell
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions 会自动：

1. 在 Windows 环境构建 exe。
2. 打包 `auto_arxiv-windows-x64.zip`。
3. 创建 GitHub Release。
4. 把 zip 上传到 Release 附件。

完成后，README 顶部的下载链接会指向最新版本。

## 项目结构

```text
src/auto_arxiv/          核心代码和桌面应用
tests/                   自动化测试
public/                  本地 Web 调试页面
scripts/build_exe.ps1    构建 Windows 桌面应用
scripts/package_release.ps1 生成 Release zip
packaging/desktop_entry.py   exe 入口
config.example.toml      示例配置
.github/workflows/       GitHub Actions
```
