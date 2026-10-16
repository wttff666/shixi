# 扫描件 OCR

知识库支持上传文字版 PDF、DOCX、Markdown、TXT；扫描版 PDF 会先标记为需要 OCR。

## 处理流程

```text
上传 PDF
-> 检测不到文字层
-> 文档状态置为待 OCR
-> 后台任务渲染页面并识别
-> 逐页保存文本与置信度
-> 管理员逐页校对
-> 保存后自动重新切片
```

## 环境

PaddleOCR 独立安装在 `D:\PaddleOCR`，由 `.env` 的以下配置指向：

```env
OCR_PYTHON=D:\PaddleOCR\venv\Scripts\python.exe
OCR_HOME=D:\PaddleOCR\models
OCR_CACHE=D:\PaddleOCR\cache
```

客户机器可用脚本安装到指定盘：

```powershell
.\tools\install_ocr.ps1 -Drive D
```

## 说明

- 文字版 PDF 优先走文本层，不触发 OCR。
- OCR 结果保留页码与置信度，低置信度内容需人工校对。
- 背景任务中断后（如服务重启）会在启动时标记为失败，可重试。
