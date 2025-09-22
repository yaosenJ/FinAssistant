# FinAssistant 项目 README

本仓库用于金融资讯与问答检索（RAG）相关的实验与评测，涵盖数据接入、向量化入库、混合检索、重排（rerank）、以及基于 LangGraph 的数据调度/Agent 实践。

> 目录中部分文件为中文内容，但存在编码问题导致显示为乱码（如 `RERDME.md`）。本文档将统一说明整体结构与各子模块职责，便于快速上手。

---

## 目录结构总览

- `congfig/` 运行配置（Milvus/MySQL/LLM 等）
- `data/` 数据集与评测结果（CSV/图片）
- `data_to_mysql_and_milvus/` 数据清洗入库与向量化脚本
- `evaluate/` RAG 评测、重排与混合检索实验脚本
- `img/` 实验截图与结果图
- `langgraph_getdata/` 基于 LangGraph/Agent 的数据调度脚本
- `log/` 运行日志
- `src/` 多个阶段性的原型目录（async0421/0422、handover0408/0414/0417）
- `test/` 测试脚本
- `README.md` 本说明文档（你正在阅读）

---

## 快速开始

### 1. 准备环境

- Python 3.10+（推荐 3.11）
- MySQL 与 Milvus（Milvus 2.5+；pymilvus 2.5+）
- 可用的 LLM/Embedding 服务（示例使用 Qwen）

创建虚拟环境并安装依赖（示意）：
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt  # 如无，请根据脚本导入补齐依赖
```

### 2. 配置文件

编辑 `congfig/config.yaml`：
- `milvus`: 主机、端口、collection 名、向量维度、检索参数（COSINE / nprobe / limit）
- `mysql`: 主机、端口、用户、密码、数据库
- `qwen`: `api_key`、`base_url`、`embedding_model`、`chat_model`
- `generation`: 采样温度/Top‑p
- `data.test_path` 与 `batch_size`

> 注意：请勿将真实的 `api_key` 与数据库密码提交至版本库。

### 3. 数据入库与向量化

进入 `data_to_mysql_and_milvus/`：
- `new_processed_daily_news.py`：抽取指定时间范围的新闻、识别字段（概念/行业/公司/来源等），写入 MySQL。
- `text_embedding_to_milvus.py`：从 MySQL 拉取指定时间范围的新闻，合并 `title+content` 为文本，生成向量并写入 Milvus。
- `text_embedding_to_milvus_hybrid_search_new.py`：建立混合检索（向量 + 关键词 BM25）所需的 Milvus 集合（如 `company_news_hybrid`）。

运行示例（时间窗口见脚本内参数）：
```bash
python data_to_mysql_and_milvus/new_processed_daily_news.py
python data_to_mysql_and_milvus/text_embedding_to_milvus.py
python data_to_mysql_and_milvus/text_embedding_to_milvus_hybrid_search_new.py
```

### 4. 评测与实验

进入 `evaluate/`：
- `evaluate_rag.py`：基础 RAG 评测（embedding/混合/重排多种组合）。
- `evaluate_rag_hybrid.py`：仅混合检索实验（embedding v3 + BM25）。
- `evaluate_rag_rerank.py`：仅重排实验（如 gte‑rerank‑v2）。
- `evaluate_rag_rerank_bge-reranker-large.py`：使用 bge‑reranker‑large 的重排实验（需本地或服务端支持）。
- `generate_qa.py` / `generate_qa_upgrade.py`：根据时间范围与筛选条件生成 QA 对。
- `hybrid_demo.py`：混合检索演示。

评测结果 CSV 位于 `data/qa_pairs`、`data/qa_pairs_update` 等目录；配套可视化见 `img/`。

### 5. 基于 LangGraph 的数据调度（可选）

`langgraph_getdata/` 包含不同阶段的主脚本与日志：
- `langgraph_main.py` / `langgraph_main_new.py` / `langgraph_main_old.py`
- 多个 `query_*.py`：行业、概念、财务科目、市场数据等查询工作流

从目录内 `README.md` 开始，按需运行，建议先在测试库或只读环境中验证。

---

## 关键数据与结果目录

- `data/qa_pairs/` 与 `data/qa_pairs_update/`：不同批次/方法的 RAG 评测结果
  - `rag_results_*_v1.csv` / `rag_results_*_v3.csv`：不同 embedding 版本
  - `*_re.csv` / `*_re_bge-reranker-large.csv`：加入重排的结果
  - `*_hybrid.csv`：混合检索（embedding v3 + BM25）
- `img/`：Milvus 集合结构与评测可视化截图
- `log/`：运行日志

---

## 代码说明（src 子目录）

`src/` 下含多个时间点/阶段的原型目录（`async0421`、`async0422`、`handover0408/0414/0417`），典型文件：
- `main.py`：主入口
- `database.py`：数据库访问
- `get_data.py`：数据拉取
- `service_api.py`：对外服务接口
- `rag_consine_date.py`：相似度/检索逻辑
- `summary_generation*.py`：摘要生成
- `llm.py`（部分目录）：模型调用封装

不同阶段目录下实现略有差异，建议以同名文件为线索查看演进。

---

## 最佳实践与注意事项

- 确认 Milvus 版本与 `pymilvus` 版本匹配（2.5+）。
- 配置文件中的敏感信息请使用环境变量或本地未纳入版本控制的覆写文件。
- 先以小批量数据测试向量化与检索，再扩大到全量。
- 重排模型（如 `bge-reranker-large`）体积与显存需求较高，评估部署条件。
- 混合检索需要在 Milvus 端建立相应 schema；参见 `text_embedding_to_milvus_hybrid_search_new.py`。

---

## 常见问题（FAQ）

- 乱码的 `RERDME.md` 文件：内容为中文说明，但因编码非 UTF‑8 导致显示异常；不影响脚本运行。
- 连接失败：检查 `congfig/config.yaml` 的主机/端口、防火墙与凭证。
- 检索效果不佳：尝试更新 embedding 模型、调参 `nprobe/limit`，或加入重排/混合检索。

---

## 许可证

见仓库根目录 `LICENSE`（若无请按企业/团队规范补充）。
