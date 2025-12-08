# DC Bot - Job Search Bot

## 專案結構

```
src/
├── __init__.py          # 套件初始化
├── config.py            # 全域配置（環境變數、LLM API 設定）
│
├── core/               # 核心業務邏輯
│   ├── __init__.py
│   ├── job104.py       # 104 人力銀行搜尋 API
│   └── mappings.py     # 參數映射表（地區、職位類別、薪資等）
│
├── llm/                # LLM 整合模組
│   ├── __init__.py
│   ├── client.py       # LLM API 呼叫客戶端
│   └── tools.py        # LLM 工具定義（Job Search Tool）
│
└── examples/           # 範例程式
    ├── __init__.py
    └── job_search.py   # LLM 工作搜尋整合範例
```

## 模組說明

### 1. `core` - 核心功能

**job104.py**
- `search_104_jobs()` - 搜尋 104 人力銀行工作機會的主要函數
- 支援多種搜尋參數：關鍵字、地區、職位類別、薪資、學歷等

**mappings.py**
- 包含所有 104 API 參數的映射表
- 支援中文名稱自動轉換為 API 代碼

### 2. `llm` - LLM 整合

**client.py**
- `call_llm()` - 呼叫 LLM API（支援 OpenAI 格式）
- `extract_tool_calls()` - 從 LLM 回應中提取工具呼叫

**tools.py**
- `JOB_SEARCH_TOOL` - LLM 工具定義（OpenAI function calling 格式）
- `execute_job_search_tool()` - 執行工作搜尋工具
- `format_job_search_results()` - 格式化搜尋結果

### 3. `examples` - 範例程式

**job_search.py**
- 展示如何使用 LLM 進行智能工作搜尋
- 包含完整的對話流程範例

## 使用方式

### 直接使用核心功能

```python
from src.core import search_104_jobs

# 搜尋 Python 工程師，台北市，薪資 50K 以上
result = search_104_jobs(
    keyword="Python",
    area=["台北市"],
    salary_min=50000
)
```

### 使用 LLM 整合

```python
from src.examples import chat_with_job_search

# 自然語言查詢
result = chat_with_job_search("幫我找台北市薪水 5 萬以上的 Python 工程師")
```

## 環境設定

1. 建立 `.env` 檔案：
```
LLM_API_KEY=your_api_key_here
LLM_API_URL=https://api.openai.com/v1/chat/completions
LLM_MODEL=gpt-5
```

2. 安裝相依套件：
```bash
pip install -r requirements.txt
```

## 支援的搜尋條件

- **地區**：全台灣所有縣市，台北市、新北市支援區級搜尋
- **職位類別**：18 大類、51 小類（經營管理、資訊科技、行銷企劃等）
- **薪資範圍**：最低/最高月薪
- **學歷要求**：高中職以下到博士
- **發布時間**：本日、3 日內、7 日內、14 日內、30 日內
- **排序方式**：符合度、日期、經歷、學歷、應徵人數、待遇
