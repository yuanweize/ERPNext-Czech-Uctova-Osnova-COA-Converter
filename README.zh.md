# ERPNext 捷克会计科目表转换器

[English](README.md) | [Česky](README.cs.md)

> **企业级双模式** 捷克会计科目表 (Účtová osnova) → ERPNext CSV 转换器。
> 支持 **商业实体 (s.r.o. / a.s.)** 和 **公共部门 (Státní pokladna)** 两种模式。

---

## ✨ 核心功能

| 功能 | 商业模式 (默认) | 公共部门模式 |
|---|---|---|
| **数据源** | 内置 2024 标准科目表 (Decree 500/2002) | 上传 data.gov.cz XML/CSV |
| **Root Types** | 资产 / 负债 / 权益 / 费用 / 收入 | 同上 |
| **Account Type** | 自动映射 (Bank, Cash, Tax, Receivable, Payable…) | 手动设置 |
| **文件上传** | 不需要 | 必需 |
| **翻译** | 🌍 AI 驱动多语言翻译 (EN/ZH/DE/…) | 同上 |

## 🚀 快速开始

```bash
# 克隆 & 安装
git clone https://github.com/YuanWeize/ERPNext-Czech-Uctova-Osnova-COA-Converter.git
cd ERPNext-Czech-Uctova-Osnova-COA-Converter
pip install -r requirements.txt
cp .env.example .env

# 生成商业版科目表 (仅捷克语，离线模式)
python erpnext_coa_translator.py --offline

# 带 AI 翻译生成 (先在 .env 中配置 API Key)
python erpnext_coa_translator.py

# 生成公共部门科目表
python erpnext_coa_translator.py --mode public_sector --input public_sector_data/uctosnova.xml --offline
```

## 🏢 商业版科目表架构

基于 **Decree 500/2002 Coll.** 的标准三层结构：

| 层级 | 示例 | 说明 |
|---|---|---|
| **类别** (Třída) | `0` | 长期资产 |
| **组** (Skupina) | `02` | 有形固定资产 |
| **综合账户** (Syntetický účet) | `022` | 有形动产及其组合 |

### Root Type 映射规则（符合 IFRS）

ERPNext 要求同一树分支中所有节点共享相同的 Root Type。转换器通过拆分处理“混合类”（2, 3, 4）—— 类级节点被省略，组直接路由到正确的 ERPNext 根节点：

| 类别 | ERPNext Root Type | 拆分逻辑 |
|---|---|---|
| 0, 1 | Asset (资产) | 全部是资产类账户 |
| 2 (21, 22, 25, 26, 29) | Asset (资产) | 现金、银行、短期金融资产 |
| 2 (23, 24) | **Liability (负债)** | 短期借款、短期融资 |
| 3 (31, 35, 39) | Asset (资产) | 应收账款、股东应收 |
| 3 (32, 33, 34, 36) | **Liability (负债)** | 应付账款、员工负债、税费 |
| 3 (37, 38) | **混合** | 按 A/P 标志拆分；少数派重新挂载 |
| 4 (41-43, 49) | **Equity (权益)** | 注册资本、留存收益 |
| 4 (45-48) | **Liability (负债)** | 准备金、长期应付 |
| 5 | Expense (费用) | 全部费用类账户 |
| 6 | Income (收入) | 全部收入类账户 |
| 7 (701/702/710) | Equity (权益) | 结转账户 |

> **混合组处理**：对于同时包含资产 (A) 和负债 (P) 科目的组（如组 33、34、37、38），多数派的 `balance_side` 决定组的 Root Type。少数派科目被直接挂载到对应的 ERPNext 根节点下。

### 自动映射的 ERPNext Account Type

- `211 库存现金 (Pokladna)` → **Cash**
- `221 银行存款 (Peněžní prostředky)` → **Bank**
- `311 应收账款-客户 (Odběratelé)` → **Receivable**
- `321 应付账款-供应商 (Dodavatelé)` → **Payable**
- `343 增值税 (DPH)` → **Tax**
- `551 折旧 (Odpisy)` → **Depreciation**
- `07x/08x 累计折旧 (Oprávky)` → **Accumulated Depreciation**

## 🌍 AI 翻译引擎

支持 **SiliconFlow**、**OpenRouter**、**OpenAI** 和 **Gemini**。在 `.env` 中配置：

```env
TRANSLATE_ENABLED=true
TRANSLATE_LANGS=en,zh
PROVIDER=siliconflow
SILICONFLOW_API_KEY=your_key_here
```

## 📋 更新日志

### v2.0 (2026-06)

- **Root Type 映射重写** — 符合 IFRS，基于 `balance_side` (A/P) 标志逐科目路由
- **混合类拆分** — 第 2/3/4 类正确拆分到 Asset、Liability 和 Equity
- **名称去重修复** — 科目名称不再包含编号前缀，避免 ERPNext “Standard with Numbers” 模式下双重编号
- **组节点编号** — 组节点现在也携带科目编号，支持排序
- **父科目编号** — CSV 现在包含父科目编号字段

## 📄 许可证

MIT License。详见 [LICENSE](LICENSE)。
