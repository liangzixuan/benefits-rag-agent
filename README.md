# Employee Benefits RAG Agent

This repository contains a lightweight Retrieval-Augmented Generation (RAG) agent that uses your PDF documents as a knowledge base and OpenAI’s APIs (Embeddings + ChatCompletion) together with FAISS for fast, semantic search.

---

## Table of Contents

1. [Overview](#overview)  
2. [Architecture](#architecture) 
3. [Prerequisites](#prerequisites)  
4. [Installation](#installation)  
5. [Configuration](#configuration)  
6. [PDF Ingestion & Indexing](#pdf-ingestion--indexing)  
7. [Running the Service](#running-the-service)  
8. [Usage](#usage)  

---

## Overview

- **Ingestion**: Reads all PDFs in `./pdfs`, splits them into overlapping text chunks.  
- **Embedding & Indexing**: Uses OpenAI’s `text-embedding-ada-002` to vectorize chunks and builds a FAISS index for cosine-similarity search.  
- **Query**: Embeds user queries, retrieves top‑K relevant chunks via FAISS, then calls ChatGPT (`gpt-3.5-turbo`) with the retrieved context to generate precise answers.  

---

## Architecture
![Architecture](https://github.com/liangzixuan/benefits-rag-agent/blob/main/architecture.png)

---

## Prerequisites

- Python 3.8+  
- macOS (Apple M-series recommended) or Linux/Windows  
- An OpenAI API key  
- Your PDF knowledge base placed in `./pdfs`  

---

## Installation

1. Clone this repository:
  ```bash
  git clone https://github.com/liangzixuan/benefits-rag-agent.git
  cd benefits-rag-agent
  ```
2. Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

## Configuration
Place all your .pdf files into the pdfs/ directory next to main.py.
Set your OpenAI key:
```bash
export OPENAI_API_KEY="sk-..."
```

## PDF Ingestion & Indexing

On startup, main.py will:

Load & chunk PDFs from ./pdfs into text slices of ~1000 characters with 200-character overlap.

Embed those chunks via OpenAI’s Embeddings API in batches.

Normalize embeddings and build a FAISS IndexFlatIP (inner product) index for cosine-similarity searches.

## Running the Service
```bash
python main.py
```
The Flask server will start on port 5001 by default.

## Usage
Send a POST to /chat with a JSON body:
```bash
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"How much does Oracle match for 401k?"}'

```
Response format:
```bash
{
  "answer": "...generated text...",
  "sources": ["file1.pdf","file2.pdf",...]
}
```

