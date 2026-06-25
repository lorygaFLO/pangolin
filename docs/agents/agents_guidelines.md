# Agent Instructions

> Operational guidelines for AI agents working on this project.
> When updating this file, keep sections small and self-contained so future rules can be appended without rewriting existing ones.

---

## 1. Role

- Act as a professional developer.

---

## 2. Core Principles

- The project must always be well-structured to guarantee **traceability** and **explainability** of the process.
- Changes introduced by users must be kept **as minimal as possible**. The process must be thought with this in mind.
- Every time a relevant change is applied and confirmed by the user, the documentation must be updated accordingly.

---

## 3. Pipeline Components

### 3.1 Processors

- Each processor represents a step of the pipeline.
- A processor can, in principle, perform any task (e.g. downloading data from a database, validating multiple files, transforming them, etc.).
- Processor parameters are **not necessarily fixed**.
- The Transformer and Validator processors must generate a **separate report for every file**, explaining:
  - why a validation failed,
  - why a transformation failed,
  - or what occurred during the process.

### 3.2 Validators

- Validators are functions that:
  - take input parameters,
  - **must return a boolean value**.

### 3.3 Transformers

- Transformers are functions that:
  - take input parameters,
  - **must return a DataFrame**.
- They are used to modify data, change formats, or apply specific transformations to the input data.

---

## 4. Project Conventions

- **Constants** shared across the project must be defined in `constants.py`.
- **`run_context`** manages information generated during a pipeline run and is intended for **dynamic values**.
- **`settings`** are intended to hold **static values only**, never dynamic ones.

---

## 5. Performance & Concurrency

- Any lazy mode, streaming mode, or concurrency approach (e.g. Polars lazy DataFrames) **must preserve traceability and monitoring** features of the pipeline.
  - Example: enabling lazy mode in Polars must still produce reports correctly, without corrupting writes or logs.
