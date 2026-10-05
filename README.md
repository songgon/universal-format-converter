# 🔄 万能格式转换器

一个本地桌面程序（Python + PySide6），支持**图片、文档、数据表格、音视频**四大类文件批量互转，无需联网，文件不出本机。

## 使用方法

双击 **`启动转换器.bat`** → 把文件拖进窗口 → 选择目标格式 → 点「开始转换」。

- 可多选/拖入多个文件批量转换
- 默认输出到原文件所在文件夹，也可指定输出文件夹
- **输出品质默认「最高」**：图片质量 100、PDF 转图片 300 DPI、音视频最高码率/近无损编码，无需自己调参数；想要更小的文件可切换「高品质 / 标准」
- 图片可勾选「合并为单个 PDF」

## 支持的转换

| 类别 | 输入格式 | 可转换为 |
|---|---|---|
| 图片 | PNG JPG WEBP BMP GIF TIFF ICO SVG HEIC(需 pillow-heif) | PNG JPG WEBP BMP GIF TIFF ICO **PDF**（多图可合并） |
| 文档 | TXT MD HTML DOCX DOC PDF RTF PPTX PPT | TXT MD HTML DOCX **PDF**（PDF 还可转 PNG/JPG 图片） |
| 数据 | CSV TSV JSON YAML XML TOML XLSX | CSV TSV XLSX JSON YAML XML TOML **MD/HTML/PDF 表格** |
| 音视频 | MP3 WAV FLAC M4A AAC OGG OPUS WMA MP4 MKV AVI MOV WEBM WMV FLV 等 | MP3 WAV FLAC M4A AAC OGG OPUS WMA / MP4 MKV MOV WEBM AVI WMV / GIF |

> **PDF 高保真引擎**：检测到本机装有 [LibreOffice](https://www.libreoffice.org/)（免费开源）时，DOCX/DOC/RTF/PPTX/PPT 转 PDF 自动走 LibreOffice 引擎，排版保真度接近原软件，且**完全免费、不碰 WPS 收费接口**；未安装时自动降级为内置轻量引擎。微软 Word 引擎为可选项（勾选启用，同样拒绝 WPS 伪装）。

## 说明

- **DOCX→PDF**：默认用内置排版引擎快速转换；勾选「使用 Word」可在装有 Microsoft Word 时获得与 Word 一致的版式（需在界面代码的转换选项中启用 `use_word`）。
- **PDF→图片**：每个页面输出一张图（文件名自动加 `_p1 _p2 …`）。
- **中文编码**：读取自动识别 UTF-8 / GBK / UTF-16；CSV 输出为 UTF-8-BOM，Excel 打开不乱码。

## 目录结构

```
格式转换器/
├─ main.py                程序入口
├─ core/                  核心转换引擎（与界面无关，可单独调用）
│  ├─ registry.py         类别识别 + 调度
│  ├─ images.py           图片模块
│  ├─ documents.py        文档模块
│  ├─ data_formats.py     数据模块
│  └─ media.py            音视频模块（ffmpeg）
├─ gui/                   PySide6 界面
│  ├─ main_window.py      外壳：侧边栏导航 + 拖拽自动路由
│  ├─ sidebar.py          可折叠侧边栏（动画）
│  ├─ convert_page.py     分类转换页（图片/文档/数据/音视频/全部）
│  ├─ theme.py            现代扁平主题样式
│  └─ worker.py           后台转换线程
├─ tests/smoke_test.py    无界面转换矩阵测试
├─ tools/ffmpeg/          内置 ffmpeg（音视频转换）
├─ 启动转换器.bat          双击启动
└─ install.bat            重装依赖
```

## 测试

```
.venv\Scripts\python.exe tests\smoke_test.py
```

会生成各类样例文件并跑一遍转换矩阵，输出 通过/失败 统计。

## 更新日志

### v1.6（系统级集成 + 绿色版）
- **右键发送到**：运行 `集成右键菜单.bat` 后，任意文件右键 → 发送到 → 万能格式转换器，直接转换（单实例：再启动会自动唤醒已开窗口并接管文件）
- **文件夹拖拽/导入**：整个文件夹拖进来，递归收集所有可转换文件
- **系统托盘**：托盘图标常驻（右键菜单：显示/退出），每批转换完成弹通知
- **转换统计**：累计次数与成功率常驻侧边栏底部
- **窗口位置记忆**：关闭时的位置和大小会恢复
- **绿色版**：`绿色版\` 文件夹（约 1.1GB，内嵌 Python 运行时 + 引擎），**双击 `万能格式转换器.exe` 约 2 秒打开**，拷到任何 Windows 10/11 x64 电脑都能跑，目标电脑无需安装 Python 或任何依赖。无需安装任何东西
- **启动优化**：绿色版从 PyInstaller 单文件方案（启动 41 秒）改为内嵌 Python 运行时，双击秒开（0.6 秒）
- 压测 v2：187 个源文件 × 全部合法组合 = 1392 次转换逐一校验，311 种组合全覆盖，全部通过
- 修复：电子书分章时吞首段、解密未加密 PDF 报错（现为幂等复制）

## 更新日志

### v1.5（颜值大改版 + 电子书）
- **全新视觉**：无边框一体化标题栏（可拖动/缩放/双击最大化）、蓝紫渐变强调色、渐变进度条、状态徽章
- **深色模式**：标题栏 🌙 按钮一键切换明暗主题，选择会被记住
- **EPUB 电子书**：TXT/Markdown/HTML/Word/RTF → EPUB（按标题智能分章）；EPUB → TXT/MD/HTML/Word（纯 Python 实现，无 DRM 解锁）
- 文件列表支持 ↑/↓ 调整顺序（决定合并 PDF 的页序）；转换显示实时耗时
- 页面套滚动容器，窗口再矮控件也不会被压缩变形

### v1.4（全面"抄作业" FlyingMouse Format）
- **Pandoc 引擎**：Markdown → Word 保留表格/嵌套列表/代码块；DOCX → Markdown 保留结构；**Markdown → PDF 走 Pandoc+LibreOffice 专业排版链**
- **PDF 工具集**：拆分（每页一个）/ 合并（多选 PDF 勾选合并）/ 加密 / 解密（AES-256），界面选目标格式后按提示输入密码
- **ZIP 批处理**：拖入压缩包自动解出可转换的文件一起转换（防路径穿越、限 1GB）
- **H.265 视频编码**：音视频页可选 H.264（兼容）/ H.265（体积约小 30%）
- **操作记忆**：记住每页上次的输出目录、目标格式、品质选择
- **双击打开结果**：转换完成的行直接双击打开输出文件
- **命令行工具**：`python convert_cli.py 文件 --to pdf [--out 目录] [--quality max]`，供脚本 / AI Agent 调用

### v1.3（借鉴 FlyingMouse Format 的引擎思路）
- **LibreOffice 高保真 PDF 引擎**：检测到 LibreOffice 后，DOCX/DOC/RTF 转 PDF 优先走 LibreOffice（排版保真，免费开源，与 WPS 收费接口无关），失败自动降级内置引擎
- **新增 PPT/PPTX 输入**：PPTX → TXT/MD/HTML/Word（python-pptx 提取逐页文本）；PPT/PPTX → PDF 走 LibreOffice
- 侧边栏底部显示引擎状态

### v1.2.1（大规模压测修复）
- 新增大规模压测 `tests/stress_matrix.py`：180 个多格式源文件 × 全部合法组合 = 1298 次转换逐一校验，295 种组合全覆盖
- 修复：WebP/ICO/HEIC 转 PDF 失败（PyMuPDF 不支持这些格式，现经 Pillow 转码嵌入）
- 修复：SVG 转换因缺少字体文件全部失败（现导入时注册系统字体，消除并行竞态）
- 修复：嵌套 JSON/YAML/TOML 转 XML 报多根节点错误（自动包一层根节点）
- 修复：转 Opus 音频因码率超上限失败（最高档降为 256k）

### v1.2
- **并行转换**：批量任务默认 4 线程同时处理，图片/文档/数据批量转换速度提升数倍
- **真·取消**：点「取消」会立即终止正在运行的 ffmpeg，而不是只跳过后续文件
- **失败重试**：批量转换出现失败时，出现「重试失败项」按钮，只重跑失败的文件
- **Word 引擎检测**：检测到本机装有 Microsoft Word 时，文档页出现「用 Word 引擎转 PDF（版式最保真）」选项
- 拖拽文件到拖拽区时有高亮反馈；输出路径计算加线程锁，并行下不会命名冲突

### v1.1
- 全新界面：可折叠侧边栏 + 分类页（图片/文档/数据/音视频/全部），拖拽自动路由
- 输出品质三档预设，默认最高品质
- 网页伪装的 .docx/.xlsx 智能嗅探并正确转换；旧版 .doc/.xls 给出明确提示
- 格式保留：转 Word/PDF/HTML 保留加粗、颜色、标题、列表、表格

## 常见问题

- **双击启动没反应**：用 `转换器(调试模式).bat` 打开查看报错信息。
- **某文件转换失败**：看窗口底部日志区的具体原因（不支持的格式组合 / 文件损坏 / 缺依赖）。
- **SVG 转 PNG 失败**：个别复杂 SVG 特性不受支持，可换用浏览器打开后截图，或转 PDF。
