# Fact-Check Agent

A PDF fact-checking assistant that extracts verifiable claims from uploaded documents, searches the web for supporting evidence, and returns a structured verdict for each claim.

The project uses a FastAPI backend for PDF processing, claim extraction, and verification, plus a Streamlit frontend for uploading PDFs and reviewing results.

## Live Demo

- Frontend: https://fact-check-agent-cwbd95mgskr3xdioavazbg.streamlit.app/
- Backend API: https://fact-check-agent.onrender.com/
- Backend docs: https://fact-check-agent.onrender.com/docs

## Features

- Upload a PDF document through a Streamlit interface.
- Extract text from machine-readable PDFs using PyMuPDF.
- Identify concrete, checkable claims such as statistics, dates, financial figures, rankings, and technical specifications.
- Search live web evidence with the Tavily API.
- Use targeted search strategies for government, policy, and pricing claims.
- Fetch direct pricing-page content for SaaS pricing claims when available.
- Verify claims with Groq-hosted Llama 3.3 70B.
- Classify each claim as `VERIFIED`, `INACCURATE`, `FALSE`, or `UNVERIFIABLE`.
- Mark future-year claims as `future_projection` and return them as unverifiable projections.
- Show confidence scores for the full report and for each individual claim.
- Attach source links to claim explanations and list URLs used during verification.
- Download the final fact-check report, including confidence scores, as a CSV file.

## Tech Stack

### Backend

- FastAPI
- Uvicorn
- PyMuPDF
- Groq Python SDK
- Tavily Search API
- HTTPX
- Beautiful Soup
- Pydantic
- python-dotenv

### Frontend

- Streamlit
- Requests
- Pandas

## Project Structure

```text
fact-check-agent/
├── backend/
│   ├── main.py              # FastAPI app and /analyze endpoint
│   ├── extractor.py         # PDF text extraction
│   ├── claim_identifier.py  # Claim extraction with Groq
│   ├── verifier.py          # Tavily search and claim verification
│   ├── models.py            # Pydantic response models
│   └── requirements.txt
├── frontend/
│   ├── app.py               # Streamlit UI
│   └── requirements.txt
├── render.yaml              # Render deployment config for backend
├── .gitignore
└── README.md
```

## How It Works

1. The user uploads a PDF in the Streamlit frontend.
2. The frontend sends the PDF to the backend `/analyze` endpoint.
3. The backend extracts text from the PDF using PyMuPDF.
4. Groq identifies verifiable claims from the extracted text.
5. Claims that reference future years are tagged as `future_projection`.
6. For each claim, Tavily searches the web for relevant evidence.
7. Pricing claims get an additional targeted pricing-page lookup and page-text extraction when available.
8. Groq evaluates the claim against the evidence and returns a verdict, explanation, primary source index, and confidence score.
9. The frontend displays summary metrics, overall confidence, claim-level confidence bars, source-linked explanations, sources, and a CSV export option.

## Requirements

- Python 3.10 or newer
- Groq API key
- Tavily API key

## Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
BACKEND_URL=http://localhost:8000
```

`BACKEND_URL` is used by the Streamlit frontend. For local development, keep it as `http://localhost:8000`.

## Local Setup

Clone the repository:

```bash
git clone https://github.com/jessica-murare/fact-check-agent.git
cd fact-check-agent
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Install frontend dependencies:

```bash
pip install -r frontend/requirements.txt
```

## Run the Backend

From the project root:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API should be available at:

```text
http://localhost:8000
```

FastAPI interactive docs:

```text
http://localhost:8000/docs
```

## Run the Frontend

Open a second terminal, activate the same virtual environment, and run:

```bash
cd frontend
streamlit run app.py
```

The Streamlit app will open in your browser, usually at:

```text
http://localhost:8501
```

## API Endpoints

### Health Check

```http
GET /
```

Returns:

```json
{
  "status": "ok",
  "message": "Fact-Check Agent is running"
}
```

### Analyze PDF

```http
POST /analyze
```

Accepts a PDF file as multipart form data:

```text
file=<uploaded_pdf>
```

Returns an analysis report:

```json
{
  "filename": "report.pdf",
  "total_claims": 3,
  "verified_count": 1,
  "inaccurate_count": 1,
  "false_count": 0,
  "unverifiable_count": 1,
  "claims": [
    {
      "id": 1,
      "text": "Example claim from the PDF",
      "category": "statistic",
      "verdict": "VERIFIED",
      "reason": "Brief explanation of the verdict — [source](https://example.com/source)",
      "correct_value": null,
      "sources": ["https://example.com/source"],
      "confidence": 85
    }
  ]
}
```

## Deployment

The included `render.yaml` config is set up for deploying the backend on Render.

Before deploying, add these environment variables in the Render dashboard:

```text
GROQ_API_KEY
TAVILY_API_KEY
```

If the frontend is deployed separately, set its `BACKEND_URL` environment variable to the deployed backend URL.

For the live Streamlit deployment, use:

```text
BACKEND_URL=https://fact-check-agent.onrender.com
```

## Limitations

- Scanned image-only PDFs are not supported unless OCR is added.
- Long PDFs are truncated during claim extraction to control token usage.
- Verification quality depends on search result relevance and model reasoning.
- Confidence scores are model-estimated and should be treated as a guide, not a mathematical certainty.
- Future projections are intentionally marked `UNVERIFIABLE` because they cannot be verified as facts yet.
- The system is designed to assist with fact-checking, not replace human review.

## Troubleshooting

### Backend says only PDFs are accepted

Make sure the uploaded file has a `.pdf` extension.

### No extractable text found

The PDF may be scanned or image-only. Add OCR support if scanned documents are required.

### Cannot reach backend

Make sure the backend is running on `http://localhost:8000` and `BACKEND_URL` is set correctly.

### No search results found

Check that `TAVILY_API_KEY` is configured and valid.

### Groq authentication error

Check that `GROQ_API_KEY` is configured and valid.

## Author

Built by [Jessica Murare](https://github.com/jessica-murare).
