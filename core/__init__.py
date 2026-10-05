"""万能格式转换器 - 核心转换引擎。

模块划分：
- registry   总调度：类别识别 / 目标格式汇总 / 文件派发
- images     图片（Pillow / SVG / HEIC / 合并 PDF）
- documents  文档（TXT / MD / HTML / DOCX / PDF / RTF）
- data_formats 数据（CSV / TSV / JSON / YAML / XML / TOML / XLSX）
- media      音视频（ffmpeg）
"""
