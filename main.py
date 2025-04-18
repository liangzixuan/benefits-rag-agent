# main.py
import os
import glob
import logging
from flask import Flask, request, jsonify
import openai
from openai import OpenAI
import PyPDF2
import faiss
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------- Configuration ---------------------
# Path to directory containing your PDF files
PDF_FOLDER = "./pdfs"
# Chunking parameters
CHUNK_SIZE = 1000      # characters per chunk
CHUNK_OVERLAP = 200    # characters overlap
EMBED_MODEL = "text-embedding-ada-002"
CHAT_MODEL = "gpt-3.5-turbo"
TOP_K = 5

# Ensure OpenAI API key is set
def getenv_or_raise(var):
    val = os.environ.get(var)
    if not val:
        logger.error(f"Missing {var} environment variable")
        raise RuntimeError(f"Missing {var} environment variable")
    return val

OPENAI_API_KEY = getenv_or_raise("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY

# --------------------- PDF Ingestion & Indexing ---------------------
# Read and chunk all PDFs into memory
def load_and_chunk_pdfs(folder):
    chunks = []
    metadata = []
    for pdf_path in glob.glob(os.path.join(folder, "*.pdf")):
        reader = PyPDF2.PdfReader(pdf_path)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        # chunk by sliding window
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

# Embed all chunks
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
# Normalize for cosine similarity
faiss.normalize_L2(embeddings)

# Build FAISS index
dim = embeddings.shape[1]
index = faiss.IndexFlatIP(dim)  # inner product == cosine after normalizing
index.add(embeddings)
logger.info("FAISS index built")

# --------------------- Flask App ---------------------
app = Flask(__name__)

@app.route("/chat", methods=["POST"])
def chat():
    req = request.get_json(silent=True) or {}
    user_q = req.get("query", "").strip()
    if not user_q:
        return jsonify(error="Missing 'query' field."), 400
    try:
        # 1) Embed query
        q_resp = client.embeddings.create(model=EMBED_MODEL, input=[user_q])
        q_vec = np.array(q_resp.data[0].embedding, dtype=np.float32)
        faiss.normalize_L2(q_vec.reshape(1, -1))

        # 2) Search FAISS
        D, I = index.search(q_vec.reshape(1, -1), TOP_K)
        hits = I[0]

        # 3) Gather top chunks
        top_chunks = [chunks[idx] for idx in hits]

        # 4) Build Chat messages
        context = " ".join(f"[{i+1}] {txt}" for i, txt in enumerate(top_chunks))
        messages = [
            {"role":"system","content":"You are an employee benefits assistant. Answer precisely using only the provided context. If unknown, say 'I don't know.'"},
            {"role":"user","content":f"Context:{context} Question: {user_q}"}
        ]

        # 5) Call ChatCompletion
        chat_resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=150
        )
        answer = chat_resp.choices[0].message.content.strip()

        return jsonify(answer=answer, sources=[doc_names[idx] for idx in hits])

    except Exception as e:
        logger.exception("Error in /chat")
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
