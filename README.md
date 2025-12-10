# 🧠 ContextBase: The Next Generation Multimodal Agent Memory Architecture

<div align="center">

![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Status](https://img.shields.io/badge/Status-In%20Development-orange)
![Multi-modal](https://img.shields.io/badge/Modality-Audio%20|%20Video%20|%20Image%20|%20Document%20|%20Text-green)

**The First "Omni-Modal" Memory Framework for AI Agents**

*Store Everything · Search Everything · Frame-Level Precision*

[中文文档](README_zh.md) • [Core Features](#-core-features) • [Architecture](#-architecture) • [Use Cases](#-use-cases)

</div>

---

## 📖 Introduction

**ContextBase is designed to build a persistent, high-fidelity, and evolutionary "Second Brain" for AI Agents.**

Most existing Memory frameworks forcibly "flatten" the rich physical world into pure text, resulting in the loss of visual details and spatio-temporal context dislocation. **ContextBase refuses this dimensional reduction.**

We are a **Multi-modal Native** memory framework engineered to ingest video, audio, and document streams in their raw, high-fidelity forms. Whether it's hundreds of hours of raw footage or a subtle visual cue in the background of a video, ContextBase delivers a closed loop from **Omni-modal Ingestion** and **Stream Storage** to **Frame-level Retrieval**.

We are not building a static database; we are building **Native Spatio-Temporal Perception** for Agents.

---

## ✨ Core Features

### 1. ♾️ Omni-Modal Storage & Retrieval
**Break the Text-to-Text barrier.** ContextBase unifies the processing paradigm for heterogeneous data.
* **Unified Input:** Seamlessly handles Video, Audio, Image, Documents, and Text.
* **Native Multi-modal Indexing:** Utilizes a "Parallel Retrieval Workflow" to index visual and auditory signals directly via vector embeddings, rather than relying solely on generated text descriptions/captions.
* **Cross-Modal Search:** Supports "Search Video by Image" and "Search Text by Audio."

### 2. 🎞️ Infinite Stream Processing
**Forget about Context Window Anxiety.**
* Designed specifically for **Long-Context** and **24/7 Continuous** Agents.
* Supports ingestion of infinite-length video and continuous audio streams.
* **Dynamic Chunking:** Built-in **Continuity Check** mechanisms ensure memory context never breaks, even when processing massive meeting records, TV series, or surveillance streams.

### 3. 🎯 0.1s Spatio-Temporal Precision
**Eliminate Timestamp Hallucinations.**
* Traditional RAG/Memory systems only tell you "which file" the answer is in. ContextBase tells you **"which minute and which second."**
* **SOTA Precision:** Retrieves and locates video/audio segments with **0.1-second accuracy**.
* **Value:** Returns precise, 0.1s key snippets (The Needle) rather than bloated 1GB files (The Haystack).

---

## 🏗️ Architecture

ContextBase draws inspiration from human cognitive processes and OS storage structures, adopting a tiered storage architecture paired with a dual-path retrieval engine.

<div align="center">
  <img src="ContextBase_Workflow_v0.png" alt="ContextBase Architecture Workflow" width="100%">
</div>

### 🧠 Memory Lifecycle
Data flows through a biomimetic processing pipeline:
1.  **Ingestion:** A unified processor extracts multi-dimensional features from heterogeneous sources.
2.  **STM (Short-Term Memory):** Handles immediate context streams, performing embedding calculations and preliminary filtering.
3.  **MTM (Medium-Term Memory):** A session-based buffer introducing a **Heat Calculation Algorithm**. The system dynamically evaluates data value based on Visit Frequency ($N_{visit}$), Interaction Depth ($L_{interaction}$), and Recency ($R_{recency}$).
4.  **LTM (Long-Term Memory):** High-heat information "crystallizes" into permanent storage (User Persona & Knowledge Base), while low-value data is pruned from working memory.

### 🔍 Precision Search Engine
Supports natural language, image, and video segment queries:
1.  **Semantic Filtering:** Rapidly screens relevant session contexts from MTM.
2.  **Vector Similarity Matching:** Performs deep scans within the LTM Knowledge Base.
3.  **Spatio-Temporal Timestamping:** Executes high-precision frame-level positioning to lock onto specific data fragments.
4.  **Result Aggregation:** Fuses retrieved video clips, background knowledge, and dialogue history into a structured **Context Dictionary** for the Agent.

---

## 🚀 Use Cases

### 1. A Truly "Understanding" Companion Agent
* **Pain Point:** Current chatbots forget everything after a conversation. You mentioned "I'm on a diet" last week, and today it still recommends high-calorie restaurants. You mentioned "I hate cilantro" three months ago, and it has completely forgotten.
* **ContextBase Memory Manifestation:**
    * **LTM (Long-Term Memory - Profile Evolution):** When you've repeatedly expressed a preference for "low-sugar diet" through voice or text in multiple conversations, the system automatically crystallizes this **high-heat information** into the `User Profile`.
    * **Memory Recall:** When you ask "What should I have for lunch today?", the Agent doesn't randomly recommend. Instead, it queries **LTM**: "I remember you're currently on a **keto diet (long-term memory)**, and last Friday (mid-term memory) you mentioned wanting to try that new salad place, but the line was too long. How about trying it today?"
    * **Value:** Evolves from "question-answer" interactions to **proactive care across time periods**.

### 2. Unified Brain for Long-Term Projects
* **Pain Point:** In a project spanning half a year, early meeting recordings, whiteboard sketches, and current code documentation are fragmented. It's difficult to ask AI: "How does our current approach differ from the ideas we had during the first brainstorming session two months ago?"
* **ContextBase Memory Manifestation:**
    * **MTM (Medium-Term Memory - Heat-Based Recall):** Although the "first brainstorming session" was two months ago, because it was the project's starting point with high **Visit Frequency ($N_{visit}$)**, it remains "warm" in MTM and hasn't been forgotten.
    * **Cross-Modal Verification:** The Agent can simultaneously retrieve the whiteboard photo from two months ago (visual memory) and the meeting recording (auditory memory), comparing them with the current design document (text input).
    * **Value:** Connects isolated time slices, prevents forgetting the project's "original intent", and provides consistent oversight across months.

### 3. Companion Learning Tutor
* **Pain Point:** Traditional educational AI doesn't know your learning curve. It doesn't know you got stuck on a concept 5 minutes ago, nor that you mastered a related foundational concept 3 days ago in another video.
* **ContextBase Memory Manifestation:**
    * **STM (Short-Term Memory - Context Awareness):** Right now, when you frown at a problem (camera captures expression or hears a sigh), STM captures your confusion.
    * **Knowledge Association:** The Agent retrieves **LTM** and discovers you spent a long time on "calculus chain rule" in a video course a month ago (high Interaction Depth $L_{interaction}$).
    * **Proactive Intervention:** "It looks like you're stuck on this step. This is similar to the 'chain rule' we reviewed last month (memory recall). Remember that red sphere demonstration animation? Let me pull it up for you."
    * **Value:** Establishes continuity in learning history, providing **personalized assistance tailored to individual needs**.

### 4. 🏠 Smart Home "Butler Memory"
* **Pain Point:** Smart speakers can only execute commands; they lack a sense of family history.
* **ContextBase Memory Manifestation:**
    * **Episodic Memory:** User: "I want to watch that video from last New Year when we all made dumplings together, I think grandma was teaching me how to fold the edges."
    * **Complex Semantic Localization:** The system doesn't search by filename, but understands "New Year (temporal context)", "everyone (multi-person recognition)", "making dumplings (action recognition)", "grandma teaching me (interaction relationship)".
    * **High-Precision Presentation:** Directly locates and plays **that 30-second heartwarming clip**, rather than dumping the entire 2-hour family recording on you.
    * **Value:** Stores family highlights, not just cold files.

---

## ⚡ Quick Start

*(Codebase is being polished and will be released shortly)*

## 🤝 Contributing

ContextBase is under active development. If you are interested in Multi-modal RAG, Agent Memory Systems, or Vector Search, please Star this repo and follow our progress.

## 📜 License

Apache 2.0