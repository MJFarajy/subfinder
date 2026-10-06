# Subdomain Finder Bot — Graphical Abstract

![Graphical Abstract](graphical_abstract/graphical_abstract.png)

> A visual architecture overview of the dual-platform (Bale/Telegram) subdomain discovery bot with persistent caching, rate limiting, and bilingual support.

---

## 🏗️ System Architecture

![System Architecture](diagrams/01_system_architecture.jpg)

```mermaid
flowchart TB
    %% ===== EXTERNAL LAYER =====
    subgraph EXT[🌐 External Interfaces]
        direction TB
        USER["👤 User\n(Bale / Telegram)"]
        AGNI[🔗 AgniOps API\napp.agniops.in/v1/search]
    end

    %% ===== PLATFORM LAYER =====
    subgraph PLAT[🤖 Platform Adapters]
        direction TB
        BALE_ADAPTER["📱 Bale Adapter\nbot/bale_client.py\nLong Polling (tapi.bale.ai)"]
        TG_ADAPTER["📱 Telegram Adapter\nbot/main.py + aiogram\nLong Polling (api.telegram.org)"]
    end

    %% ===== CORE LAYER =====
    subgraph CORE[⚙️ Core Pipeline]
        direction TB
        ROUTER["🎯 Update Router\n(bale_handlers.py / handlers.py)"]
        
        subgraph CMD[📋 Commands]
            START[/start/]
            HELP[/help/]
            LANG[/language/]
        end
        
        PROCESSOR["🔍 Domain Processor\nbot/utils.py\nnormalize_domain()"]
        CACHE[💾 Dual-Layer Cache\nbot/cache.py]
        RATE[⏱️ Rate Limiter\nbot/rate_limit.py]
        API_CLIENT[🌐 API Client\nbot/api_client.py]
    end

    %% ===== STORAGE LAYER =====
    subgraph STORE[💿 Persistent Storage]
        direction TB
        LANG_STORE[(🗄️ user_languages.json\nLanguage Preferences)]
        CACHE_DB[(🗄️ cache.db\nSQLite L2 Cache)]
    end

    %% ===== CONFIG =====
    CONFIG["⚙️ Config\nbot/config.py\n(.env driven)"]

    %% ===== CONNECTIONS =====
    USER -->|Messages / Callbacks| BALE_ADAPTER
    USER -->|Messages / Callbacks| TG_ADAPTER
    
    BALE_ADAPTER -->|Updates| ROUTER
    TG_ADAPTER -->|Updates| ROUTER
    
    ROUTER -->|Commands| CMD
    ROUTER -->|Domain Input| PROCESSOR
    
    PROCESSOR -->|Normalized Domain| CACHE
    CACHE -->|Miss| RATE
    CACHE -->|Hit| FORMAT[📤 Formatter\nSorted, Deduped, Counted]
    
    RATE -->|Queued Request| API_CLIENT
    API_CLIENT -->|HTTP GET /v1/search?domain=| AGNI
    AGNI -->|Plain Text: subdomain per line| API_CLIENT
    API_CLIENT -->|Raw Results| CACHE
    CACHE --> FORMAT
    
    CACHE -.->|L1 Memory / L2 Disk| CACHE_DB
    ROUTER -.->|Get/Set Language| LANG_STORE
    
    CONFIG -.->|Settings| BALE_ADAPTER
    CONFIG -.->|Settings| TG_ADAPTER
    CONFIG -.->|Settings| CACHE
    CONFIG -.->|Settings| RATE
    CONFIG -.->|Settings| API_CLIENT

    %% ===== STYLING =====
    classDef ext fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    classDef plat fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef core fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef store fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef config fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    
    class USER,AGNI ext
    class BALE_ADAPTER,TG_ADAPTER plat
    class ROUTER,CMD,PROCESSOR,CACHE,RATE,API_CLIENT,FORMAT core
    class LANG_STORE,CACHE_DB store
    class CONFIG config
```

---

## 🔄 Request Flow Sequence

![Request Flow Sequence](diagrams/02_request_flow_sequence.jpg)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant P as Platform<br/>(Bale/Telegram)
    participant R as Router
    participant N as Normalizer
    participant C as Cache (L1+L2)
    participant L as Rate Limiter
    participant A as API Client
    participant X as AgniOps API

    U->>P: Sends domain (e.g., "example.com")
    P->>R: Delivers update
    R->>N: normalize_domain()
    N-->>R: Clean domain ("example.com")
    R->>C: lookup(domain)
    
    alt Cache HIT
        C-->>R: Cached subdomain list
        R->>P: Formatted response
        P->>U: Results ✓
    else Cache MISS
        C-->>R: Miss
        R->>L: acquire_slot()
        L-->>R: Slot granted / queued
        
        alt Queued
            R->>U: "⏳ Queued: position N"
            L->>R: Slot available
        end
        
        R->>A: fetch_subdomains(domain)
        A->>X: GET /v1/search?domain=example.com
        X-->>A: Plain text (subdomain per line)
        A-->>R: Raw subdomain list
        R->>C: store(domain, results)
        R->>P: Formatted response
        P->>U: Results ✓
    end
```

---

## 🧩 Key Components Detail

![Key Components Detail](diagrams/03_key_components_detail.jpg)

```mermaid
flowchart LR
    subgraph CACHE_SYS[💾 Dual-Layer Cache]
        L1[L1: In-Memory Dict\n~instant access]
        L2["L2: SQLite (data/cache.db)\nSurvives restarts"]
        TTL["TTL: 600s (configurable)\nAuto-cleanup on startup"]
    end

    subgraph RATE_SYS[⏱️ Rate Limiting System]
        SW[Sliding Window\n60 req / 60 sec]
        HQ[Request Queue\nFIFO + status updates]
        H429[429 Handler\nRetry-Aware Backoff]
    end

    subgraph API_SYS[🌐 API Client]
        RETRY[Exponential Backoff\nmax 3 retries]
        TIMEOUT[180s timeout\nconfigurable]
        PARSE[Text→List Parser\nDedup + Sort]
    end

    subgraph I18N[🌍 Bilingual System]
        EN[English]
        FA["Persian (Farsi)"]
        PERSIST[Persistent: user_languages.json]
        AUTO[Auto-detect:\nBale→FA, Telegram→language_code]
    end

    L1 <--> L2
    SW --> HQ
    HQ --> H429
    RETRY --> TIMEOUT
    TIMEOUT --> PARSE
    EN <--> FA
    FA --> PERSIST
    EN --> PERSIST
    AUTO --> FA
    AUTO --> EN
```

---

## 📊 Feature Matrix

| Feature | Implementation | Location |
|---------|---------------|----------|
| **Dual Platform** | Bale (no VPN) + Telegram (proxy) | `bale_main.py` / `main.py` |
| **Subdomain Discovery** | AgniOps API (GET /v1/search) | `api_client.py` |
| **Input Normalization** | URL/domain/port/path stripping | `utils.py:normalize_domain()` |
| **L1 + L2 Cache** | Memory dict + SQLite + TTL | `cache.py` |
| **Global Rate Limit** | Sliding window 60/min + queue | `rate_limit.py` |
| **Queue UX** | Position + periodic updates | `rate_limit.py` + handlers |
| **429 Handling** | Header-aware backoff | `api_client.py` + `rate_limit.py` |
| **Bilingual (EN/FA)** | Inline keyboard + persistence | `i18n.py` + `language_store.py` |
| **Large Results** | `.txt` file upload | `handlers.py` / `bale_handlers.py` |
| **Auto-Restart** | Shell/bat scripts + systemd/task | `scripts/` |
| **Docker** | Multi-stage build | `Dockerfile` |
| **Testing** | Pytest + async mocks | `tests/` |

---

## 🚀 Deployment Topology

![Deployment Topology](diagrams/04_deployment_topology.jpg)

```mermaid
flowchart TB
    subgraph DEV[Development]
        VENV[venv/]
        PY[python -m bot.bale_main]
    end

    subgraph PROD[Production Options]
        DOCKER[🐳 Docker Container]
        SYSTEMD[🐧 systemd Service]
        TASK[🪟 Windows Task Scheduler]
        FOREVER[🔁 run_forever.sh/.bat]
    end

    subgraph INFRA[Infrastructure]
        ENV[.env file]
        DATA[data/]
        LOGS[stdout/logs]
    end

    DEV -->|Build| DOCKER
    DOCKER -->|Mount| ENV
    DOCKER -->|Volume| DATA
    DOCKER -->|Stdout| LOGS
    
    SYSTEMD -->|ExecStart| PY
    TASK -->|Action| PY
    FOREVER -->|Loop| PY
    
    PY -->|Reads| ENV
    PY -->|Writes| DATA
    PY -->|Logs| LOGS
```

---

## 🎯 Design Principles

![Design Principles Mindmap](diagrams/05_design_principles_mindmap.jpg)

```mermaid
mindmap
  root((Subdomain Finder Bot))
    Reliability
      Graceful Degradation
      Per-message Tasks
      Global Error Handler
      Clean Shutdown
    Performance
      Async/Await (httpx/aiogram)
      Dual-Layer Cache
      Connection Pooling
      IPv4 Optimization
    Observability
      Structured Logging
      Token Masking
      Startup Self-Check
    Security
      .env isolation
      No secrets in logs
      Optional allowlist
      Per-user rate limit
    User Experience
      Bilingual (EN/FA)
      Queue transparency
      File fallback
      Inline keyboards
```

---

## 📝 Quick Reference: Data Flow

```
User Input
    │
    ▼
┌─────────────────────┐
│ normalize_domain()  │  ← strips scheme, www, path, port, query
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Cache Lookup (L1→L2)│  ← key: normalized domain
└─────────┬───────────┘
    Hit  /  Miss
    │         │
    ▼         ▼
Return    Rate Limit
Cached    Acquire Slot
          │
          ▼
    ┌─────────────┐
    │ API Request │  ← GET https://app.agniops.in/v1/search?domain=
    │  (retries)  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Parse &     │  ← split lines, dedupe, sort, count
    │ Format      │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Store in    │  ← L1 + L2 with TTL
    │ Cache       │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Send to     │  ← Markdown (TG) / Markdown (Bale)
    │ Platform    │     >4000 chars → .txt file
    └─────────────┘
```

---

*Generated for **Subdomain Finder Bot** — A robust, bilingual, dual-platform subdomain discovery service.*