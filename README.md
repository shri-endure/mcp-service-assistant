# MCP Service Resolution Assistant

An intelligent, production-ready AI service assistant built with the **Model Context Protocol (MCP)**, **Gemini / Groq LLMs**, **FastAPI**, **SQLite**, and a modern **Vanilla JS/CSS frontend**.

---

## Project Structure
MCP SERVICE AI ASSISTANT:
The MCP Service Resolution Assistant is an intelligent, end-to-end customer support and booking platform for home appliances and computer repairs.
Instead of functioning as a simple text chatbot, it acts as an Actionable AI Agent: it analyzes user problems, looks up official manufacturer repair manuals, provides authorized customer care numbers, searches the web for real-time local technicians in the user's specific city/locality, and books appointments directly into a database with conflict-free calendar time slots.
The project implements the Model Context Protocol (MCP) architecture created by Anthropic, combined with a dual-LLM fallback mechanism and real-time web search.


```
mcp-service-assistant/
│
├── server/
│   ├── mcp_server.py
│   └── tools/
│       ├── problem_analyzer.py
│       ├── service_search.py
│       ├── provider_details.py
│       ├── availability.py
│       ├── appointment.py
│       └── cancellation.py
│
├── client/
│   └── mcp_client.py
│
├── api/
│   └── main.py
│
├── database/
│   └── database.py
│
├── data/
│   └── seed_data.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── tests/
│   ├── test_tools.py
│   └── test_api.py
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Key Components

### 1. Server (`server/`)
- **`server/mcp_server.py`**: FastMCP server that exposes tools and resources (`service://categories`, `service://faqs`) over `stdio`.
- **`server/tools/problem_analyzer.py`**: Analyzes problem queries across AC Repair, Laptop Repair, Plumbing, and Washing Machine Repair.
- **`server/tools/service_search.py`**: Searches local verified providers and web-listed external providers via Tavily API.
- **`server/tools/provider_details.py`**: Retrieves complete ratings, locations, price tiers, and contact numbers.
- **`server/tools/availability.py`**: Checks real-time slot availability for dates and returns available/booked slots.
- **`server/tools/appointment.py`**: Books appointments in SQLite and prevents double-booking conflicts.
- **`server/tools/cancellation.py`**: Cancels existing appointments by appointment ID.

### 2. Client (`client/`)
- **`client/mcp_client.py`**: Implements the MCP client using `mcp.ClientSession` over `stdio` subprocess communication.
- **`client/ai_agent.py`**: High-level conversational agent orchestrating Gemini with Groq fallback and MCP tool execution.

### 3. API (`api/`)
- **`api/main.py`**: FastAPI web application providing:
  - `POST /chat`: Natural language assistant endpoint with reasoning logs.
  - `GET /health`: Health status of database, MCP server, and active LLM models.
  - `GET /booked-slots`: Real-time map of booked slots per provider.
  - `POST /book-appointment`: Direct appointment booking with customer modal details.
  - `POST /cancel-appointment`: Direct appointment cancellation.
  - Static file serving for `frontend/index.html`, `style.css`, and `app.js`.

### 4. Database & Data (`database/` & `data/`)
- **`database/database.py`**: SQLite database manager maintaining tables: `providers`, `services`, `availability`, `appointments`.
- **`data/seed_data.py`**: Verified provider data across North and South Goa with ratings and pricing.

### 5. Frontend (`frontend/`)
- **`frontend/index.html`**: Clean, accessible responsive UI layout.
- **`frontend/style.css`**: Modern styling featuring dark glassmorphism, responsive grid, faded booked slots, and disabled input states during task execution.
- **`frontend/app.js`**: Real-time interactive logic:
  - Single active task lock (disables textarea, send button, chips).
  - Cross-tab real-time sync for booked slots (faded indication for unavailable slots).
  - Direct customer booking modal submission and confirmation receipts.

### 6. Tests (`tests/`)
- **`tests/test_tools.py`**: Unit and integration test suite verifying all 6 modular tools, error handling conditions (STEP 26), and repair scenarios 1-7 (STEP 27).
- **`tests/test_api.py`**: API endpoint test suite verifying health check, slot retrieval, appointment booking flow, duplicate booking prevention, and static file serving.

---

## Setup & Installation

### 1. Clone & Setup Virtual Environment
```bash
git clone <repo-url>
cd mcp-service-assistant

# Create and activate virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

### 3. Run the Application
Start the FastAPI server:
```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at:
```
http://127.0.0.1:8000
```

---

## Running Tests

### 1. Test Modular MCP Tools
```bash
python tests/test_tools.py
```

### 2. Test FastAPI Endpoints
```bash
python tests/test_api.py
```
