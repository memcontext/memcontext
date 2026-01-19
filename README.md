# 🧠 MemContext: Next-Generation Multi-modal Agent Memory Framework

<div align="center">

![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/Status-In%20Development-orange)
![Multi-modal](https://img.shields.io/badge/Modality-Audio%20|%20Video%20|%20Image%20|%20Document%20|%20Text-green)

**The First Full-Modal Cross-Platform Memory Framework for AI Agents**

*Store Everything · Search Everything · Frame-Level Positioning · Multi-Platform Support*

[中文](README_zh.md) • [Core Features](#-core-features) • [Architecture](#-architecture) • [Use Cases](#-use-cases) • [Quick Start](#-quick-start)

</div>

---

## 📖 Introduction

**MemContext is dedicated to building a persistent, high-fidelity, evolvable, and cross-platform full-modal memory repository for AI Agents.**

Existing Agent Memory frameworks are mostly text-centric, often failing to preserve information from videos, audio, and documents in their original form. This leads to the loss of multi-modal content and context misalignment when recalling information across different timelines.

Designed with a **"Full-Modal Native"** principle, MemContext provides end-to-end capabilities for video, audio, and document streams—from **full-modal input and streaming storage to frame-level retrieval**. Whether it's a massive library of long-term footage or easily overlooked visual details, everything can be reliably written and precisely retrieved when needed.

Furthermore, MemContext is deeply adapted to mainstream ecosystems like **n8n, Coze, MCP, and Skills**. Through a plugin-based mechanism, it empowers existing Agent workflows with integrated cross-platform memory capabilities.

---

## ✨ Core Features

### 1. ♾️ Full-Modal Storage & Retrieval

**Beyond the limits of Text-to-Text.** MemContext unifies the processing paradigm for heterogeneous data.

* **Input:** Unified processing of video, audio, images, documents, and text.
* **Multi-modal Native Indexing:** Adopts a "Parallel Retrieval Workflow," establishing vector indexes directly for visual and auditory signals, rather than relying solely on their textual descriptions.
* **Cross-Modal Retrieval:** Supports "Search Video by Image" and "Search Text by Audio."

### 2. 🎞️ Infinite Stream Processing

**Forget the anxiety of limited context windows.**

* Designed specifically for **Long Context Data** and **24/7 Continuous Operation**.
* Supports the ingestion of infinite-length videos and continuous audio streams.
* **Dynamic Chunking:** Built-in continuity checks ensure that memory context does not break when processing massive meeting records, TV series, or surveillance streams.

### 3. 🎯 0.1s Spatiotemporal Precision

**Stop hallucinating timestamps.**

* Traditional RAG and Memory systems can only tell you "which file the answer is in"; MemContext tells you **"at which minute and second the answer occurs."**
* **SOTA Precision:** Capable of retrieving and positioning video/audio segments with **0.1-second accuracy**.
* **Value:** Instead of returning a bloated 1GB file, it returns the precise 0.1-second key segment, achieving true "needle in a haystack" retrieval.

### 4. 🤖 Seamless Multi-Platform Integration

**Out-of-the-box, deep compatibility with mainstream agent platforms.**

* **n8n Support:** Bring persistent, retrievable multi-modal memory to automation workflows.
* **Coze Support:** Empower Coze Agents with cross-session knowledge and context continuity.
* **MCP Support:** Facilitate enterprise-level agent management of multi-user and multi-session memory data.
* **Claude Skills Support:** Empower Claude assistants, significantly enhancing context depth and data invocation capabilities.
* **Unified API:** Regardless of the platform, integration is easy via standard RESTful APIs or SDKs.
* **Value:** Make your multi-modal memory capabilities truly "plug-and-play," adaptable across platforms, scenarios, and ecosystems without barriers.

---

## 🏗️ Architecture

MemContext draws inspiration from human cognitive processes and operating system storage structures, adopting a tiered storage architecture paired with a dual-retrieval engine.

<div align="center">
<img src="assets/MemContext_Workflow_v0.png" alt="MemContext Architecture Workflow" width="100%">
</div>

### 🧠 Memory Lifecycle

The journey of data through the memory pipeline:

1. **Multi-modal Input:** A unified processor extracts multi-dimensional features from heterogeneous data.
2. **STM (Short-Term Memory):** Handles immediate context streams, performing Embedding calculations and preliminary filtering.
3. **MTM (Medium-Term Memory):** A session-based buffer introducing a **Heat Calculation Algorithm**. The system dynamically judges data value based on Visit Frequency (), Interaction Depth (), and Recency ().
4. **LTM (Long-Term Memory):** High-heat information "crystallizes" into permanent storage (User Profiles & Knowledge Bases), while low-value data is discarded from working memory.

### 🔍 Precision Retrieval Engine

Supports multiple query forms including natural language, images, and video segments:

1. **Semantic Filtering:** Quickly filters relevant session contexts from MTM.
2. **Vector Similarity Matching:** Performs a deep full-repository scan in the LTM knowledge base.
3. **Spatiotemporal Positioning:** Executes high-precision frame-level positioning to lock onto specific data segments.
4. **Result Aggregation:** Fuses retrieved video slices, background knowledge, and dialogue history into a structured context list returned to the Agent.

---

## 🚀 Use Cases

### 1. Personalized AI Agent

* **Pain Point:** Current chatbots forget as soon as the chat ends. You said "I'm on a diet" last week, but today it recommends a high-calorie restaurant; you mentioned hating cilantro three months ago, and it has no recollection.
* **MemContext Implementation:**
* **LTM (Profile Evolution):** When you reveal a preference for a "low-sugar diet" via voice or text across multiple conversations, the system automatically crystallizes this **high-heat information** into your `User Profile`.
* **Memory Recall:** When you ask "What's for lunch today?", the Agent won't recommend randomly. Instead, it calls upon **LTM**: "I remember you are on a **Keto diet (Long-Term Memory)**, and last Friday (**Medium-Term Memory**) you mentioned wanting to try that new salad place but the line was too long. Shall we try that today?"
* **Value:** Evolution from simple Q&A to **proactive care spanning time cycles**.



### 2. Integrated Brain for Long-Cycle Projects

* **Pain Point:** In a six-month project, early meeting recordings, whiteboard sketches, and current code documentation are disconnected. It's hard to ask AI: "How does our current solution deviate from the ideas in our first brainstorming session two months ago?"
* **MemContext Implementation:**
* **MTM (Heat Recall):** Although the "first brainstorming session" was two months ago, because it was the project's starting point, its **Visit Frequency ()** is high, keeping it "warm" in MTM and preventing it from being forgotten.
* **Cross-Modal Verification:** The Agent can simultaneously retrieve the whiteboard photo (Visual Memory) and the meeting recording (Auditory Memory) from two months ago, comparing them with current design documents (Text Input).
* **Value:** Connects isolated time slices, prevents forgetting the "original intent" of the project, and provides consistency supervision across months.



### 3. Companion Learning Tutor

* **Pain Point:** Traditional education AI doesn't know your learning curve. It doesn't know you got stuck on a point 5 minutes ago, nor does it know you mastered a foundational concept in a related video 3 days ago.
* **MemContext Implementation:**
* **STM (Context Awareness):** Right now, as you frown at a problem (camera captures expression or hears a sigh), STM captures your confusion.
* **Knowledge Association:** The Agent searches **LTM** and finds that you lingered for a long time on the "Chain Rule in Calculus" in a video course a month ago (High Interaction Depth ).
* **Proactive Intervention:** "It looks like you're stuck on this step. This is very similar to the 'Chain Rule' we reviewed last month (**Memory Recall**). Remember that red sphere animation? Let me pull that up for you."
* **Value:** Establishes continuity in learning history, providing **personalized assistance based on aptitude**.



### 4. Smart Home "Butler Memory"

* **Pain Point:** Smart speakers only execute commands; they have no sense of family history.
* **MemContext Implementation:**
* **Episodic Memory:** User: "I want to watch that video of us making dumplings last New Year, I think Grandma was teaching me how to pleat them."
* **Complex Semantic Positioning:** The system doesn't search for filenames but understands "New Year (Time Scope)," "Us (Multi-person Recognition)," "Making Dumplings (Action Recognition)," and "Grandma teaching me (Interaction Relationship)."
* **High-Precision Presentation:** It directly locates and plays **that specific 30-second heartwarming clip**, rather than throwing a 2-hour home video at you.
* **Value:** Storing the family's highlight moments, not just cold files.



---

## 📋 Prerequisites

* **Python 3.10+**
* **flask>=2.0.0,<3.0.0**

---

## ⚡ Quick Start

1. Create a Python Virtual Environment

```bash
conda create -n memcontext python=3.10 -y
conda activate memcontext

```

2. Install Dependencies
Import requirements in the root directory:

```bash
pip install -r requirements.txt

```

3. Configure Secrets

Create a `.env` file in the `memdemo` directory and add the LLM API KEY and other secrets.
Example:

```ini
# LLM API Configuration (For content analysis and intelligent dialogue)
LLM_API_KEY=YOUR-API-KEY
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-1-6-flash-250828

# Vectorization Embedding API Configuration (For Vector Database)
EMBEDDING_API_KEY=YOUR-API-KEY
EMBEDDING_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
EMBEDDING_MODEL=doubao-embedding-large-text-250515

# SiliconFlow API Configuration (For Audio Understanding Model)
SILICONFLOW_API_KEY=YOUR-API-KEY
SILICONFLOW_MODEL=TeleAI/TeleSpeechASR

# Audio Transcription Configuration
ENABLE_AUDIO_TRANSCRIPTION=true

```

4. Run the AI Dialogue Demo with Memory Capabilities

```bash
cd memdemo
python app.py    # Default port 5019

```

Open http://localhost:5019/ in your browser to see the login interface. Enter a username to chat with the AI and experience the memory features.

## 🤝 Contributing

The core functions of MemContext are currently under intensive development. If you are interested in Multi-modal Agent Memory systems, feel free to Star the repo and follow our progress.

## 📜 License

Apache 2.0