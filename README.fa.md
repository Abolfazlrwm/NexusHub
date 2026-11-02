<div align="center">

# NexusHub

**پلتفرم متن‌باز و self-hosted برای ساخت، اجرا، ارزیابی و مدیریت AI Agent ها.**

FastAPI · Next.js · PostgreSQL + pgvector · Redis — با موتور [nexusagent](packages/nexusagent)

[![engine-ci](https://github.com/Abolfazlrwm/NexusHub/actions/workflows/engine-ci.yml/badge.svg)](https://github.com/Abolfazlrwm/NexusHub/actions/workflows/engine-ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](packages/nexusagent/pyproject.toml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[English](README.md) · فارسی

</div>

---

## NexusHub چیست؟

NexusHub یک پلتفرم متن‌باز و **self-hosted برای ساخت، اجرا، ارزیابی و مدیریت AI Agent** ها است — چیزی شبیه Dify یا LangSmith، ولی سبک‌تر، ساده‌تر و کاملاً روی زیرساخت خودت.

کل ایده‌ی پروژه این است: **اگر نتوانی agent ات را بسنجی، نمی‌توانی آن را منتشر کنی.** به همین دلیل ارزیابی (eval) و ردیابی (trace) افزودنی دیرهنگام نیستند — از روز اول بخشی از هسته‌ی سیستم هستند.

| دردسر رایج | راه‌حل NexusHub |
| --- | --- |
| پلتفرم‌های ابریِ agent، داده‌هایت را بیرون از شرکت می‌فرستند | همه‌چیز روی سرور خودت اجرا می‌شود — فقط `docker compose up` بزن |
| ابزارهای متن‌بازِ agent معمولاً eval ندارند | موتور eval در هسته: دیتاست YAML، اجرای موازی، امتیازدهی با LLM-as-judge، مقایسه نسخه‌ها کنار هم |
| یک ابزار برای RAG، یک ابزار برای eval، یک ابزار برای trace | یک پلتفرم واحد: سازنده‌ی agent، پلی‌گراند چت، RAG، trace و eval همه کنار هم |

## معماری

```text
                    ┌─────────────────────────┐
                    │   Dashboard (Next.js)   │
                    │ builder · chat · traces │
                    └────────────┬────────────┘
                                 │ REST + SSE
                    ┌────────────▼────────────┐
                    │   API Gateway (FastAPI) │
                    │  API-key auth · OpenAPI │
                    └──┬─────────┬─────────┬──┘
                       │         │         │
        ┌──────────────▼──┐  ┌───▼─────────┴───┐
        │  Agent Runtime  │  │    Job Queue    │
        │  (nexusagent)   │  │  (Redis + arq)  │
        │  tool calling · │  └───┬─────────────┘
        │  memory · stream│      │
        └──────┬──────────┘      │
               │                 │
        ┌──────▼─────────────────▼───────┐
        │ RAG pipeline: upload → chunk → │
        │ embed → pgvector → retrieval   │
        └──────────────┬─────────────────┘
        ┌──────────────▼─────────────────┐
        │ Eval engine: YAML datasets →   │
        │ parallel runs → scoring →      │
        │ comparison reports             │
        └──────────────┬─────────────────┘
        ┌──────────────▼─────────────────┐
        │ PostgreSQL + pgvector          │
        │ agents · runs · documents ·    │
        │ evals · api keys               │
        └────────────────────────────────┘
```

طرح کامل کامپوننت‌ها و جریان داده‌ها را در [docs/architecture.md](docs/architecture.md) ببینید.

## ساختار ریپو

```text
NexusHub/
├── packages/
│   └── nexusagent/      # موتور اجرای agent (پکیج مستقل پایتونی)
├── apps/
│   ├── api/             # گیت‌وی FastAPI     (مایل‌استون بعدی)
│   └── dashboard/       # داشبورد Next.js    (مایل‌استون بعدی)
├── docs/                # مستندات معماری و طراحی
├── docker-compose.yml   # خودمیزبانی با یک دستور (مایل‌استون بعدی)
└── Makefile             # تسک‌های توسعه (lint / typecheck / test)
```

موتور یک پکیج مستقل و قابل انتشار است که پلتفرم از آن استفاده می‌کند: موتور به‌تنهایی کار می‌کند و پلتفرم آن را به محصول تبدیل می‌کند.

## وضعیت و نقشه راه

NexusHub در حال توسعه‌ی فعال است. کارها روی فیچربرنچ انجام می‌شوند و مایل‌استون‌به‌مایل‌استون در `main` مرج می‌شوند.

- [ ] **موتور nexusagent** — تایپ‌ها، tool calling، حافظه، استریم، trace
- [ ] **ابزارهای داخلی** — ماشین‌حساب، تاریخ/ساعت، UUID
- [ ] **گیت‌وی FastAPI** — مدیریت agent ها، چت با استریم SSE، احراز هویت با API key
- [ ] **اجرای‌ها و trace ها** — تاریخچه‌ی کامل اجراها با trace مرحله‌به‌مرحله
- [ ] **پایپ‌لاین RAG** — دریافت سند، امبدینگ، بازیابی با pgvector
- [ ] **صف کار** — ورکرهای async با Redis + arq
- [ ] **موتور ارزیابی** — دیتاست YAML، اجرای موازی، امتیازدهی، مقایسه
- [ ] **داشبورد Next.js** — سازنده‌ی agent، پلی‌گراند، نمایشگر trace، گزارش eval
- [ ] **خودمیزبانی با یک دستور** — docker compose

## شروع سریع — موتور

`nexusagent` با **هر endpoint سازگار با OpenAI** کار می‌کند: OpenAI، OpenRouter،
vLLM، LM Studio یا Ollama لوکال.

```bash
git clone https://github.com/Abolfazlrwm/NexusHub.git
cd NexusHub
pip install -e "packages/nexusagent[dev]"
```

```python
import asyncio

from nexusagent import Agent, AgentConfig, OpenAICompatProvider


async def main() -> None:
    provider = OpenAICompatProvider(
        model="gpt-4o-mini",                    # یا "qwen2.5" با Ollama
        api_key="sk-...",                       # برای مدل‌های لوکال: "ollama"
        base_url="https://api.openai.com/v1",   # یا "http://localhost:11434/v1"
    )
    agent = Agent(
        config=AgentConfig(system_prompt="You are a precise assistant."),
        provider=provider,
    )
    result = await agent.run("What is 37 * 142? Use the calculator.")
    print(result.output)              # پاسخ نهایی
    print(result.usage.total_tokens)  # محاسبه‌ی توکن
    print(result.trace.model_dump())  # هر فراخوانی مدل و ابزار


asyncio.run(main())
```

## مستندات

- [مرور معماری](docs/architecture.md) (انگلیسی)
- [مستندات موتور nexusagent](packages/nexusagent/README.md) (انگلیسی)
- [راهنمای مشارکت](CONTRIBUTING.md)
- [تغییرات](CHANGELOG.md)

## مشارکت

ایssue و پول‌ریکوئست خوش‌آمد هستند. برای محیط توسعه، نام‌گذاری برنچ و قواعد کامیت [CONTRIBUTING.md](CONTRIBUTING.md) را بخوانید.

## لایسنس

[MIT](LICENSE) © 2026 Abolfazlrwm
