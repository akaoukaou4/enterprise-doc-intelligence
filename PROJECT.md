# Enterprise AI Document Intelligence Platform

> **What this file is:** the description of the project: the idea, the purpose, the scope, the principles, and where it can grow. It is deliberately **not technical**.
> **Where the technical details live:** in `ROADMAP.md` (stack decisions, phases, tasks, progress). Live status is tracked there, not here.
> **Status:** V1, core implementation.

---

## 1. The project in one paragraph

The **Enterprise AI Document Intelligence Platform** lets people upload their organization's documents (HR policies, security policies, technical documentation, handbooks, reports, procedures, contracts, any PDF) and then **ask questions in plain language**. The platform finds the relevant passages in the documents and writes an answer **based only on those passages**, and it **shows where the answer came from** (which document, which page). If the documents don't contain the answer, it says so instead of making something up.

---

## 2. The problem it solves

Every organization accumulates documents: policies, procedures, manuals, contracts. The knowledge is in there, but:

- **Finding it takes time.** People open several PDFs and scan page after page for one answer.
- **Keyword search is weak.** If you search for "vacation" but the policy says "annual leave", you may find nothing.
- **Generic AI chatbots can't be trusted with company knowledge.** They don't know the organization's documents, and they can confidently invent answers.

This platform answers questions **from the organization's own documents**, with **sources you can check**, and admits when it doesn't know.

### A concrete example

> **Question:** "How many days of notice do I need to give before taking annual leave?"
> **Answer:** "Employees must request annual leave at least 14 days in advance through their manager. *(Source: HR_Policy.pdf, page 7)*"
>
> **Question:** "What is the company's policy on pet insurance?"
> **Answer:** "I couldn't find this in the uploaded documents."

(The numbers and document names are illustrative.)

---

## 3. What the platform does

From a user's point of view, there are three things:

1. **Upload documents.** Add PDFs and see when each one is ready to be used.
2. **Ask questions.** Type a question in everyday language, in the language of the documents.
3. **Get a trustworthy answer.** Read a clear answer together with the **sources** it came from, so it can be verified, and a clear "not found" when the documents don't cover the question.

---

## 4. How it works, in simple words

The platform follows the same logic a careful person would use:

```text
Documents                              A question
   │                                       │
   ▼                                       ▼
1. Read each document, page by page    4. Understand what the question means
2. Cut it into small readable pieces   5. Find the pieces whose meaning is closest
3. Capture the meaning of each piece   6. Give only those pieces to the AI
   and store it                        7. The AI writes an answer from them
                                       8. Show the answer and its sources
```

The key idea is that the AI is **not asked to remember everything**. It is handed only the few passages that matter for this particular question, and told to answer from them alone. This approach is called **RAG** (Retrieval-Augmented Generation). It is what makes the answers grounded and checkable.

---

## 5. Who it is for

- **Employees and teams** who need quick, reliable answers from internal documents.
- **HR, IT, security and compliance people** whose policies are asked about over and over.
- **The project owner's learning and portfolio goals:** this is also a demonstration project (see section 7) that shows real engineering skills to teachers, recruiters and interviewers.

---

## 6. Core idea and philosophy

- This is **not** a machine-learning training project. We do **not** train models. We **use existing AI models** and build a useful application around them.
- The guiding chain is: **Data → Retrieval → AI → Backend → Cloud.**
- The AI model is **one component** of a larger system. The real learning is in connecting it properly: getting the data in, finding the right information, building a reliable service around it, and putting it online.
- A good answer depends more on **good data handling and good retrieval** than on the AI model alone.

---

## 7. What this project is meant to demonstrate

**Data engineering:** taking in unstructured documents, building a processing pipeline, storing files and information, orchestrating the work, searching by meaning.

**AI / GenAI engineering:** using existing AI models through their interfaces, understanding retrieval-augmented generation, constructing prompts, grounding answers in real data, returning citations, and understanding what AI models can and cannot do (including making things up, usage limits, and untrusted text).

**Backend engineering:** building a clean, validated, well-structured service that connects storage, search and AI, and handles errors gracefully.

**Cloud:** understanding cloud storage and deployment, running the application online, and being aware of cost.

**Software engineering:** version control, reproducible environments with containers, configuration and secrets handled safely, tests, project structure and documentation.

---

## 8. Guiding principles

1. **Do not over-engineer V1.** This is a student project: it must be **simple enough to finish**. A working, understandable V1 beats an impressive, unfinished one.
2. **Every technology must earn its place.** We add a tool only when it solves a real problem in the project, never because it looks good on a CV. Examples of things deliberately **left out**: Kubernetes, Kafka, Terraform, agent frameworks, microservices, advanced monitoring, complex authentication, custom model training.
3. **Grounded or silent.** An answer must come from the documents and show its sources. When the documents don't contain the answer, the platform says so.
4. **Honest about limits.** What doesn't work yet (and why) is written down, not hidden.
5. **Understand, don't just copy.** The owner is a student who wants to understand every step: what each part does, why it was chosen, and what the trade-offs are.
6. **Low cost by design.** The project is built to run on free or low-cost services, and we stay aware of usage limits and cloud costs.
7. **One phase at a time.** Each phase has a clear definition of "done", and we finish it before moving on.

---

## 9. V1 scope

### Included in V1

- Uploading, listing and deleting PDF documents, with a clear processing status for each
- Turning documents into searchable knowledge, page by page, so sources can name the page
- Asking questions and getting **grounded answers with citations**
- A clear **"not found in the documents"** behavior, and friendly handling of usage limits
- A **simple web interface** so a non-technical person can use it without any developer tools
- Automated processing of uploaded documents
- Tests, a one-command way to run the whole system, and deployment online
- Clear documentation of the project, its decisions and its limits

### Not included in V1

Reading scanned/image-only PDFs (no OCR), file types other than PDF, user accounts and per-user permissions, conversation memory (each question stands alone), live "typing" answers, advanced search techniques, multiple organizations, advanced monitoring, and anything involving training AI models.

---

## 10. What "V1 is done" looks like

V1 is complete when all of this is true:

- A user can upload a PDF, wait until it is ready, ask a question in the web interface, and receive an answer **with its sources**.
- Questions the documents can't answer get an honest "not found" instead of an invented answer.
- If the AI service's free usage limit is reached, the user sees a clear, friendly message instead of a crash.
- The documents are processed automatically after upload.
- The project's tests pass, and the whole system starts with one command on a fresh machine.
- The application is reachable online, with its running cost under control.
- Anyone who has never seen the project can understand it, run it and judge it from its documentation in about five minutes.

---

## 11. Known limitations of V1

These are accepted on purpose and will be documented honestly:

- **Scanned documents** (pages that are just pictures of text) are detected but not read.
- **Complex layouts and tables** in PDFs may not be read perfectly.
- **Answers are only as good as the search step.** If the right passage isn't found, the answer will be incomplete or "not found".
- **Each passage is small**, so the AI sees limited surrounding context.
- **Free AI usage has limits:** a small number of questions per day, sometimes slow responses, and the provider may use free-tier inputs to improve its products. That is why **only public or sample documents are used during development**.
- **Each question stands alone:** no follow-up conversation memory.
- **Light protection only:** V1 is a demonstration, not a hardened enterprise product.

---

## 12. Where the project can grow (not part of V1)

These are ideas for later versions. V1 is built so they can be added without starting over, but **none of them should be built now**.

### Version 2 ideas: making it better

| Idea | Benefit |
|------|---------|
| A stronger search/understanding model | Finds the right passages more reliably |
| Combining meaning-based and keyword search, plus re-ranking results | Better precision, especially for exact terms and numbers |
| A stronger or higher-capacity AI model | Better answers and no daily free-usage limit |
| Giving the AI more surrounding text for each passage | Fuller, more accurate answers |
| Reading scanned documents (OCR) | Works on scanned PDFs |
| More document types (Word, web pages, text) | Broader usefulness |
| User accounts and per-user access to documents | Safe for real teams |
| Conversation memory and follow-up questions | More natural use |
| Answers that appear as they are written | Better experience |
| Automatic measurement of answer quality | Proof that changes improve things |
| A more polished web interface | Production-grade look and feel |
| A managed database and automated deployment and monitoring | Less manual work, more reliability |

### Version 3 ideas: going further

Multiple organizations using the same platform, AI "agents" that carry out multi-step tasks, infrastructure defined as code, large-scale deployment tooling, advanced monitoring, quality dashboards, and fine-tuning. These only make sense **when a real problem demands them**.

---

## 13. Context and constraints

- **It is a student project:** realistic, finishable, and focused on learning.
- **Low budget:** free tiers and limited cloud credits shape the choices. The cloud account is created only when it is needed, because the free credits last a limited time.
- **Responsible data use:** because free AI services may use inputs to improve their products, only public or sample documents are used while developing.
- **Honesty over polish:** limitations, trade-offs and measured results are documented, since they show engineering maturity.

---

## 14. How we work (for the owner and for any AI assistant)

1. **Start by reading** this file (the "what and why") and then `ROADMAP.md` (the "how and when") to know the current phase.
2. **One phase at a time.** Never pull Version 2 or 3 ideas into V1.
3. **Do not add tools or technologies** that are not already in the roadmap's decisions. If something new seems needed, explain the problem it solves and **ask the owner first**.
4. **Do not silently change a decision.** Propose it, get approval, then update the roadmap (and this file if the vision or scope changes).
5. **Verify facts that change quickly** (AI model names, free-usage limits, cloud prices and rules) instead of relying on memory, and **never invent** facts, numbers or sources.
6. **Be honest** about what doesn't work, what is untested and what is a known limitation.
7. **Teach while building:** explain new terms and trade-offs simply, and prefer the simplest thing that works.
8. **When something is unclear, ask one focused question**, especially before anything expensive or hard to undo.
9. **Keep each document in its role** (see section 15). Don't copy content from one file into another; link to it instead.

---

## 15. Where things live

| Document | Its purpose |
|----------|-------------|
| **`PROJECT.md`** (this file) | The idea: what we are building, why, for whom, what is in and out of scope, the principles, and where it can grow. Non-technical and stable. |
| **`ROADMAP.md`** | The execution: technology decisions and the reasons behind them, the phases from environment setup to the end of V1, task checklists, definitions of done, progress, changelog and open questions. Updated every work session. |
| **`README.md`** *(written at the end)* | The public face: how to run the project, its architecture diagram and a quick demo. |
| **`docs/`** *(grows as we build)* | Supporting notes: measured results, limitations, deployment steps, provider limits, decisions. |
