# ERPNext Czech Účtová Osnova (COA Converter)（中文）

- 作用：将捷克公共部门会计科目表（Směrná účtová osnova）转换为 ERPNext 可导入的多语 CSV（捷克/英语/中文），并处理科目编号冲突、名称长度限制。
- 输入：官方 XML `uctosnova.xml`（示例已附）。
- 输出：`erpnext_coa_multilingual_YYYYMMDD_HHMM.csv`（带时间戳）。
- 翻译：SiliconFlow + Qwen，IPSAS/CAS 术语优先；支持缓存、重试、离线模式（跳过 API）。

## 快速开始
1) 创建虚拟环境并激活。
2) `pip install -r requirements.txt`
3) 复制 `.env.example` 为 `.env`，填入 `SILICONFLOW_API_KEY`（或使用 `--offline`）。
4) 运行：
```bash
python erpnext_coa_translator.py
```

## 配置项（.env）
- `SILICONFLOW_API_KEY`（翻译必填）
- `MODEL_ID` 默认 `Qwen/Qwen2.5-72B-Instruct`
- `MAX_WORKERS` / `BATCH_SIZE` 并发控制
- `CURRENCY` 默认 CZK
- `LIMIT` ERPNext 名称长度限制（默认 131）
- `OUTPUT_PREFIX` 输出文件前缀

## 数据源
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd

## 其它
- `translation_cache.json` 保留做示例；`translation_cache_Qwen/` 已忽略。
- MIT 许可证，见 LICENSE。
