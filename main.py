# main.py
import os
import glob
import logging
import json
from flask import Flask, request, jsonify
import openai
from openai import OpenAI
import PyPDF2
import faiss
import numpy as np
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------- Configuration ---------------------
PDF_FOLDER = "./pdfs"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_MODEL = "text-embedding-ada-002"
CHAT_MODEL = "gpt-3.5-turbo-1106"
TOP_K = 5
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
APPOINTMENT_TOKEN = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'

def getenv_or_raise(var):
    val = os.environ.get(var)
    if not val:
        logger.error(f"Missing {var} environment variable")
        raise RuntimeError(f"Missing {var} environment variable")
    return val

OPENAI_API_KEY = getenv_or_raise("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY

# --------------------- PDF Ingestion & Indexing ---------------------
def load_and_chunk_pdfs(folder):
    chunks, metadata = [], []
    for pdf_path in glob.glob(os.path.join(folder, "*.pdf")):
        reader = PyPDF2.PdfReader(pdf_path)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            metadata.append(os.path.basename(pdf_path))
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks, metadata

logger.info("Loading and chunking PDFs...")
chunks, doc_names = load_and_chunk_pdfs(PDF_FOLDER)
logger.info(f"Created {len(chunks)} chunks")

def embed_texts(texts):
    embeddings = []
    for i in range(0, len(texts), 16):
        batch = texts[i : i + 16]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        for d in resp.data:
            embeddings.append(d.embedding)
    return np.array(embeddings, dtype=np.float32)

logger.info("Embedding chunks...")
embeddings = embed_texts(chunks)
faiss.normalize_L2(embeddings)
dim = embeddings.shape[1]
index = faiss.IndexFlatIP(dim)
index.add(embeddings)
logger.info("FAISS index built")

# --------------------- Tool Functions ---------------------
def lookup_benefit_term(term):
    glossary = {
        "HSA": "Health Savings Account lets you save pre-tax money for medical expenses.",
        "PPO": "Preferred Provider Organization is a type of health insurance plan."
    }
    return glossary.get(term, f"Definition for '{term}' not found.")

def calculate_benefit_cost(plan_type, monthly_premium, deductible):
    try:
        total_cost = 12 * float(monthly_premium) + float(deductible)
        return f"The estimated annual cost for a {plan_type} plan is ${total_cost:.2f}."
    except:
        return "Invalid input for benefit calculation."

def get_calendar_service():
    creds = None
    if os.path.exists(APPOINTMENT_TOKEN):
        with open(APPOINTMENT_TOKEN, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(APPOINTMENT_TOKEN, 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def schedule_appointment(date, time, reason):
    try:
        service = get_calendar_service()
        event = {
            'summary': 'Benefits Appointment',
            'description': reason,
            'start': {
                'dateTime': f"{date}T{time}:00",
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': f"{date}T{time}:00",
                'timeZone': 'America/New_York',
            }
        }
        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Appointment scheduled successfully. View it here: {event.get('htmlLink')}"
    except Exception as e:
        logger.exception("Error scheduling appointment with Google Calendar")
        return "Failed to schedule the appointment. Please try again later."

function_defs = [
    {
        "name": "lookup_benefit_term",
        "description": "Look up a benefit term from the internal glossary",
        "parameters": {
            "type": "object",
            "properties": {
                "term": {"type": "string"}
            },
            "required": ["term"]
        }
    },
    {
        "name": "calculate_benefit_cost",
        "description": "Calculate the estimated annual cost of a health plan",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_type": {"type": "string"},
                "monthly_premium": {"type": "number"},
                "deductible": {"type": "number"}
            },
            "required": ["plan_type", "monthly_premium", "deductible"]
        }
    },
    {
        "name": "schedule_appointment",
        "description": "Schedule a user appointment for benefits-related assistance",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["date", "time", "reason"]
        }
    }
]

# --------------------- Flask App ---------------------
app = Flask(__name__)

@app.route("/chat", methods=["POST"])
def chat():
    req = request.get_json(silent=True) or {}
    user_q = req.get("query", "").strip()
    if not user_q:
        return jsonify(error="Missing 'query' field."), 400
    try:
        q_resp = client.embeddings.create(model=EMBED_MODEL, input=[user_q])
        q_vec = np.array(q_resp.data[0].embedding, dtype=np.float32)
        faiss.normalize_L2(q_vec.reshape(1, -1))
        D, I = index.search(q_vec.reshape(1, -1), TOP_K)
        hits = I[0]
        top_chunks = [chunks[idx] for idx in hits]

        context = " ".join(f"[{i+1}] {txt}" for i, txt in enumerate(top_chunks))
        messages = [
            {"role": "system", "content": "You are an employee benefits assistant. Answer precisely using the provided context or call a function if needed."},
            {"role": "user", "content": f"Context: {context} Question: {user_q}"}
        ]

        chat_resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            functions=function_defs,
            function_call="auto",
            temperature=0.2,
            max_tokens=150
        )

        message = chat_resp.choices[0].message

        if message.function_call:
            fn_name = message.function_call.name
            args = json.loads(message.function_call.arguments)
            logger.info(f"Function call requested: {fn_name}({args})")

            if fn_name == "lookup_benefit_term":
                result = lookup_benefit_term(**args)
            elif fn_name == "calculate_benefit_cost":
                result = calculate_benefit_cost(**args)
            elif fn_name == "schedule_appointment":
                result = schedule_appointment(**args)
            else:
                result = f"Function '{fn_name}' is not implemented."

            messages.append(message)
            messages.append({"role": "function", "name": fn_name, "content": result})

            follow_up = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=150
            )
            answer = follow_up.choices[0].message.content.strip()
            return jsonify(answer=answer, sources=[])

        else:
            answer = message.content.strip()
            return jsonify(answer=answer, sources=[doc_names[idx] for idx in hits])

    except Exception as e:
        logger.exception("Error in /chat")
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)