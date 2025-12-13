"""Job Detail Analysis Workflow."""

import re
import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
from ..llm.client import call_llm
from .prompt import JOB_DETAIL_ANALYSIS_PROMPT


def extract_url_from_query(query: str) -> Optional[str]:
    """
    從查詢字串中提取 URL。

    Args:
        query: 用戶查詢字串

    Returns:
        提取到的 URL，如果沒有則返回 None
    """
    # URL 正則表達式
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, query)
    return match.group(0) if match else None


def validate_url_security(url: str) -> bool:
    """
    驗證 URL 的安全性，防止 SSRF 等攻擊。

    Args:
        url: 要驗證的 URL

    Returns:
        URL 是否安全
    """
    try:
        parsed = urlparse(url)

        # 只允許 http 和 https 協議
        if parsed.scheme not in ['http', 'https']:
            print(f"⚠️  不支援的協議：{parsed.scheme}")
            return False

        # 禁止訪問內網 IP 和 localhost
        hostname = parsed.hostname
        if not hostname:
            return False

        # 禁止訪問 localhost 和內網 IP
        blocked_hosts = ['localhost', '127.0.0.1', '0.0.0.0']
        if hostname.lower() in blocked_hosts:
            print("⚠️  禁止訪問 localhost")
            return False

        # 禁止訪問內網 IP 段（10.x.x.x, 172.16-31.x.x, 192.168.x.x）
        if hostname.startswith(('10.', '172.', '192.168.')):
            print("⚠️  禁止訪問內網 IP")
            return False

        return True

    except Exception as e:
        print(f"⚠️  URL 驗證失敗：{e}")
        return False


def extract_104_job_content(soup: BeautifulSoup) -> str:
    """
    專門提取 104 職缺頁面的內容。

    Args:
        soup: BeautifulSoup 物件

    Returns:
        提取的職缺資訊
    """
    info_parts = []

    try:
        # 提取職位標題
        title = soup.find('h1')
        if title:
            info_parts.append(f"職位：{title.get_text(strip=True)}")

        # 提取公司名稱
        company = soup.find('a', class_='company')
        if not company:
            company = soup.find(attrs={'data-qa': 'company-name'})
        if company:
            info_parts.append(f"公司：{company.get_text(strip=True)}")

        # 提取薪資
        salary = soup.find(attrs={'data-qa': 'salary'})
        if not salary:
            salary = soup.find('span', class_='salary')
        if salary:
            info_parts.append(f"薪資：{salary.get_text(strip=True)}")

        # 提取工作地點
        location = soup.find(attrs={'data-qa': 'job-location'})
        if not location:
            location = soup.find('span', class_='location')
        if location:
            info_parts.append(f"地點：{location.get_text(strip=True)}")

        # 提取職位描述
        description = soup.find('div', class_='job-description')
        if not description:
            description = soup.find(attrs={'data-qa': 'job-description'})
        if description:
            desc_text = description.get_text(strip=True)[:500]  # 限制長度
            info_parts.append(f"職位描述：{desc_text}")

        return "\n".join(info_parts) if info_parts else ""

    except Exception as e:
        print(f"⚠️  104 內容提取失敗：{e}")
        return ""


def extract_general_content(soup: BeautifulSoup) -> str:
    """
    提取一般網站的主要內容。

    Args:
        soup: BeautifulSoup 物件

    Returns:
        提取的文字內容
    """
    try:
        # 移除 script 和 style 標籤
        for script in soup(['script', 'style', 'header', 'footer', 'nav']):
            script.decompose()

        # 提取標題
        title = soup.find('title')
        title_text = title.get_text(strip=True) if title else ""

        # 提取 h1
        h1 = soup.find('h1')
        h1_text = h1.get_text(strip=True) if h1 else ""

        # 提取主要內容區域
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)

        # 清理多餘空白
        text = re.sub(r'\s+', ' ', text).strip()

        # 組合資訊
        info_parts = []
        if title_text:
            info_parts.append(f"頁面標題：{title_text}")
        if h1_text and h1_text != title_text:
            info_parts.append(f"主標題：{h1_text}")
        if text:
            # 限制內容長度
            content_preview = text[:1500]
            info_parts.append(f"內容：{content_preview}")

        return "\n".join(info_parts)

    except Exception as e:
        print(f"⚠️  通用內容提取失敗：{e}")
        return ""


def is_dynamic_website(url: str) -> bool:
    """
    判斷是否為需要 JavaScript 渲染的動態網站。

    Args:
        url: 網頁 URL

    Returns:
        是否為動態網站
    """
    # 需要使用 Playwright 的網站列表
    dynamic_domains = [
        '104.com.tw',
        # 未來可以添加更多需要動態渲染的網站
    ]
    return any(domain in url for domain in dynamic_domains)


async def extract_104_dynamic_content(page: Page) -> str:
    """
    使用 Playwright 提取 104 職缺頁面的結構化內容。

    此函數會提取完整的職位資訊，包括：
    - 基本資訊：職位、公司、更新日期
    - 工作內容：完整的工作描述和要求
    - 職務類別
    - 工作條件：待遇、性質、地點、時段等
    - 條件要求：學歷、經歷、技能、工具等
    - 福利制度
    - 聯絡方式

    Args:
        page: Playwright Page 物件

    Returns:
        格式化的職缺資訊字串
    """
    try:
        # 等待頁面完全載入
        await page.wait_for_selector('body', timeout=15000)
        await page.wait_for_timeout(3000)

        # 獲取整個頁面的文本內容
        body_text = await page.locator('body').inner_text()
        lines = [line.strip() for line in body_text.split('\n') if line.strip()]

        # 嘗試從行中找到職位和公司
        title = None
        company = None

        # 提取 h1 標題作為職位
        try:
            h1 = await page.locator('h1').first.inner_text()
            if h1 and len(h1) < 100:  # 確保是合理的職位名稱
                title = h1.strip()
        except Exception:
            pass

        # 如果沒找到 h1，從文本中推斷
        if not title:
            for i, line in enumerate(lines):
                if '公司' in line and i > 0:
                    # 上一行可能是職位
                    potential_title = lines[i-1]
                    if len(potential_title) < 50 and not any(x in potential_title for x in ['工作', '登入', 'APP', '職涯']):
                        title = potential_title
                        break

        # 查找公司名稱（通常在開頭部分）
        for i, line in enumerate(lines[:30]):
            if '股份有限公司' in line or '有限公司' in line:
                if len(line) < 50:  # 確保是公司名稱而不是地址
                    company = line
                    break

        # 構建結構化資訊
        structured_info = []

        if title:
            structured_info.append(f"【職位名稱】\n{title}\n")

        if company:
            structured_info.append(f"【公司名稱】\n{company}\n")

        # 提取各個關鍵section
        sections_to_extract = {
            '工作內容': ('工作內容', '職務類別'),
            '職務類別': ('職務類別', '工作待遇'),
            '工作待遇': ('工作待遇', '工作性質'),
            '工作條件': ('工作性質', '條件要求'),
            '條件要求': ('條件要求', '公司環境照片'),
            '福利制度': ('福利制度', '聯絡方式'),
            '聯絡方式': ('聯絡方式', '104人力銀行提醒您'),
        }

        for section_name, (start_marker, end_marker) in sections_to_extract.items():
            section_content = extract_section(lines, start_marker, end_marker)
            if section_content:
                structured_info.append(f"【{section_name}】\n{section_content}\n")

        # 如果成功提取了結構化資訊，返回
        if len(structured_info) > 2:  # 至少有標題、公司和一個section
            result = "\n".join(structured_info)
            print(f"✅ 成功提取結構化內容（{len(result)} 字元）")
            return result

        # 如果結構化提取失敗，返回處理過的完整文本
        print("⚠️  結構化提取不完整，使用完整文本")
        # 清理文本：移除導航、頁尾等無關內容
        cleaned_lines = []
        skip_patterns = ['登入', '註冊', '104人力銀行', 'APP', '所有服務', '智能客服',
                        '常見問題', '隱私中心', '建議瀏覽器', '適合你大展身手',
                        '我適合這份工作嗎', '這些工作也很適合你']

        in_content = False
        for line in lines:
            # 開始內容標記
            if any(marker in line for marker in ['工作內容', '職務類別', '公司名稱']) and not in_content:
                in_content = True

            # 跳過無關內容
            if any(pattern in line for pattern in skip_patterns):
                continue

            # 結束標記
            if '104人力銀行提醒您' in line or '職場安全提醒' in line:
                break

            if in_content and line:
                cleaned_lines.append(line)

        cleaned_text = '\n'.join(cleaned_lines)
        print(f"✅ 提取清理後的文本（{len(cleaned_text)} 字元）")
        return cleaned_text

    except Exception as e:
        print(f"⚠️  104 動態內容提取失敗：{e}")
        import traceback
        traceback.print_exc()
        return ""


def extract_section(lines: list, start_marker: str, end_marker: str) -> str:
    """
    從文本行列表中提取特定section的內容。

    Args:
        lines: 文本行列表
        start_marker: section開始標記
        end_marker: section結束標記

    Returns:
        提取的section內容
    """
    content_lines = []
    capturing = False

    # 過濾模式：移除冗餘的鏈接文字（僅用於職務類別section）
    link_filter_patterns = [
        '認識', '更多', '相關工作', '-求職面試工作問題',
        '職務分析', '技能證照', '薪資和學習'
    ]

    for line in lines:
        if start_marker in line:
            capturing = True
            # 如果這行只有標記，跳過；否則包含這行
            if line.strip() != start_marker:
                content_lines.append(line)
            continue

        if capturing:
            if end_marker in line:
                break

            # 對於職務類別section，過濾掉鏈接文字
            if start_marker == '職務類別':
                if any(pattern in line for pattern in link_filter_patterns):
                    continue
                # 過濾掉只有頓號的行
                if line.strip() == '、':
                    continue

            content_lines.append(line)

    return '\n'.join(content_lines).strip()


async def fetch_dynamic_content(url: str) -> Optional[str]:
    """
    使用 Playwright 提取動態網站內容（異步版本）。

    Args:
        url: 網頁 URL

    Returns:
        提取的內容，失敗則返回 None
    """
    try:
        print(f"🎭 使用 Playwright 提取動態內容：{url}")

        async with async_playwright() as p:
            # 啟動瀏覽器（headless 模式）
            browser = await p.chromium.launch(headless=True)

            # 創建上下文，禁用不必要的資源以提高速度
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=False,  # 驗證 SSL
            )

            # 阻止不必要的資源載入以提高速度
            await context.route("**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}", lambda route: route.abort())

            # 創建頁面
            page = await context.new_page()

            # 設置超時
            page.set_default_timeout(30000)  # 30 秒

            # 訪問頁面 - 使用 domcontentloaded 而不是 networkidle（更快）
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # 判斷是否為 104 網站
            is_104 = '104.com.tw' in url

            if is_104:
                print("📋 使用 104 專用提取器")
                content = await extract_104_dynamic_content(page)
            else:
                print("📄 使用通用動態內容提取器")
                # 通用提取：等待頁面穩定後獲取文字
                await page.wait_for_timeout(2000)
                body_text = await page.locator('body').inner_text()
                body_text = re.sub(r'\s+', ' ', body_text).strip()[:1500]
                content = f"頁面內容：{body_text}"

            # 關閉瀏覽器
            await browser.close()

            if not content:
                print("⚠️  未能提取到有效內容")
                return None

            print(f"✅ 成功提取動態內容（{len(content)} 字元）")
            return content

    except PlaywrightTimeout:
        print("⚠️  Playwright 請求超時")
        return None
    except Exception as e:
        print(f"⚠️  Playwright 提取失敗：{e}")
        return None


def fetch_static_content(url: str) -> Optional[str]:
    """
    使用 requests + BeautifulSoup 提取靜態網站內容（原有邏輯）。

    Args:
        url: 網頁 URL

    Returns:
        提取的內容，失敗則返回 None
    """
    try:
        print(f"🌐 使用靜態方法提取網頁內容：{url}")

        # 設定請求標頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        }

        # 發送請求
        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            allow_redirects=True,
            verify=True,
            stream=True
        )
        response.raise_for_status()

        # 限制內容大小
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 5 * 1024 * 1024:
            print("⚠️  網頁內容過大，超過 5MB 限制")
            return None

        # 獲取內容
        content = b''
        size = 0
        max_size = 5 * 1024 * 1024
        for chunk in response.iter_content(chunk_size=8192):
            size += len(chunk)
            if size > max_size:
                print("⚠️  下載內容超過大小限制")
                break
            content += chunk

        # 解析 HTML
        soup = BeautifulSoup(content, 'html.parser')
        extracted_content = extract_general_content(soup)

        if not extracted_content:
            print("⚠️  未能提取到有效內容")
            return None

        # 長度限制
        if len(extracted_content) > 2000:
            extracted_content = extracted_content[:2000] + "..."

        print(f"✅ 成功提取靜態內容（{len(extracted_content)} 字元）")
        return extracted_content

    except requests.Timeout:
        print("⚠️  請求超時")
        return None
    except requests.RequestException as e:
        print(f"⚠️  網頁提取失敗：{e}")
        return None
    except Exception as e:
        print(f"⚠️  處理網頁內容時發生錯誤：{e}")
        return None


async def fetch_webpage_content(url: str) -> Optional[str]:
    """
    智能提取網頁內容，自動選擇靜態或動態提取方法（異步版本）。

    流程：
    1. URL 安全驗證
    2. 判斷是否為動態網站（如 104.com.tw）
    3. 動態網站 → 使用 Playwright（異步）
    4. 靜態網站 → 使用 requests + BeautifulSoup

    資安防護措施：
    - URL 安全驗證（防止 SSRF 攻擊）
    - 限制請求大小
    - 設定超時時間
    - 驗證 SSL 證書

    Args:
        url: 網頁 URL

    Returns:
        網頁的文字內容摘要，如果失敗則返回 None
    """
    # 資安檢查：驗證 URL 安全性
    if not validate_url_security(url):
        print("❌ URL 安全驗證失敗")
        return None

    # 判斷是否為動態網站
    if is_dynamic_website(url):
        # 使用 Playwright 提取動態內容（異步）
        return await fetch_dynamic_content(url)
    else:
        # 使用靜態方法提取內容
        return fetch_static_content(url)


async def analyze_job_detail(job_query: str) -> Dict[str, Any]:
    """
    使用 LLM 分析特定職缺的詳細資訊。

    此函數利用 LLM 內建的 web search 功能，查詢職缺相關的公司背景、
    職位要求、員工評價等資訊，並生成分析報告。

    Args:
        job_query: 職缺查詢資訊，應包含職位名稱、公司名稱等基本描述。
                  範例：「某科技公司的 Python 後端工程師」或
                        「104 職缺連結：https://www.104.com.tw/job/xxxxx」

    Returns:
        包含分析結果的字典：
        {
            "job_query": str,                # 輸入的職缺查詢
            "analysis_report": str,          # LLM 生成的分析報告
            "processing_time": float,        # 處理時間（秒）
            "token_usage": Dict,             # Token 使用量統計
        }

    Example:
        >>> result = analyze_job_detail("某科技公司的 Python 後端工程師")
        >>> print(result["analysis_report"])

        >>> # 也可以直接傳入 104 連結
        >>> result = analyze_job_detail("https://www.104.com.tw/job/xxxxx")
        >>> print(result["analysis_report"])
    """

    # 準備返回結果
    result = {
        "job_query": job_query,
        "analysis_report": "",
        "processing_time": 0.0,
        "token_usage": {},
        "webpage_content": None,  # 新增：儲存提取的網頁內容
    }

    # 檢查是否包含 URL
    url = extract_url_from_query(job_query)
    webpage_content = None

    if url:
        # 如果包含 URL，先提取網頁內容
        webpage_content = await fetch_webpage_content(url)
        print(webpage_content)
        result["webpage_content"] = webpage_content

    # 準備職缺資訊
    if webpage_content:
        # 如果成功提取網頁內容，將其加入查詢資訊
        formatted_info = f"""用戶查詢：{job_query}

從職缺網頁提取的基本資訊：
{webpage_content}

請基於以上資訊進行更深入的分析。"""
    else:
        # 沒有網頁內容，直接使用原始查詢
        formatted_info = job_query

    # 使用 LLM 進行分析
    print("🤖 分析職缺詳細資訊中...")

    messages = [
        {
            "role": "system",
            "content": JOB_DETAIL_ANALYSIS_PROMPT.format(job_info=formatted_info),
        },
        {
            "role": "user",
            "content": "請開始分析這個職缺。",
        },
    ]

    start_time = time.time()
    llm_response = call_llm(messages=messages)
    processing_time = time.time() - start_time

    result["processing_time"] = processing_time

    # 顯示處理時間和 token 使用量
    print(f"⏱️  分析耗時: {processing_time:.2f} 秒")
    if "usage" in llm_response:
        usage = llm_response["usage"]
        result["token_usage"] = {
            "total": usage.get("total_tokens", 0),
            "prompt": usage.get("prompt_tokens", 0),
            "completion": usage.get("completion_tokens", 0),
        }
        print(f"📊 Token 使用量: {usage.get('total_tokens', 0)} tokens "
              f"(prompt: {usage.get('prompt_tokens', 0)}, "
              f"completion: {usage.get('completion_tokens', 0)})")

    # 提取分析報告
    result["analysis_report"] = llm_response["choices"][0]["message"]["content"]
    print(f"📝 報告長度：{len(result['analysis_report'])} 字元")

    return result
