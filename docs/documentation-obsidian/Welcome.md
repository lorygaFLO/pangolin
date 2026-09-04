# Welcome to Pangolin

**Pangolin** is an installable library + CLI for building data pipelines, built on [Prefect](https://www.prefect.io/) and powered by [Polars](https://pola.rs/). The intent is not just to provide a working example, but a solid, opinionated foundation for a real production project — without having to design the scaffolding yourself. `pip install git+https://github.com/lorygaFLO/pangolin.git`, run `pangolin init` in an empty folder, and you get a sensible folder layout, a config-driven engine, and a clear extension model, so your first commit can focus on business logic rather than plumbing. See [[Getting Started]].

This documentation is structured as an [Obsidian](https://obsidian.md/) vault. For the best experience — including linked pages, graph view, and sidebar navigation — open the `docs/documentation-obsidian/` folder as a vault in Obsidian.
---

## How to Navigate This Documentation

Use the sidebar or the links below to explore each topic:

| Page                              | What You'll Learn                                                                                        |
| --------------------------------- | -------------------------------------------------------------------------------------------------------- |
| [[Architecture Overview]]         | High-level design, folder layout, and how data flows through the pipeline                                |
| [[Getting Started]]               | Environment setup, `.env` configuration, and running the pipeline locally                                |
| [[Docker Deployment]]             | Running with Docker (local, docker-local, cloud modes), security warning on UI access                    |
| [[Pipeline Configuration]]        | How pipelines are auto-discovered from `pipelines/`, and how to wire or add stages                        |
| [[Data Structure & DataFacility]] | How `data_structure.yaml` maps folders/files and how to use `DataFacility` in code to do data operations |
| [[Registry Reference]]            | Full guide on writing registry YAML files for each step                                                  |
| [[Writing Validators]]            | How to create and register a new validator function                                                      |
| [[Writing Transformers]]          | How to create and register a new transformer function                                                    |
| [[Creating a New Processor]]      | How to extend the engine with a custom processor type                                                    |
| [[Adding Custom Settings]]        | How to add your own project-specific settings (e.g. `S.TRAINING_EPOCHS`) via `custom/settings.py`         |
| [[Future Developments]]           | Planned improvements: testing strategy, cloud/Docker support, aggregation example, deeper Prefect usage  |

---

## Quick Overview (Example Pipeline)

The pipeline structure is **fully configurable** — you can add, remove, or reorder steps to match your needs. `pangolin init` scaffolds this example flow, runnable out of the box:

```
CSV files in data/input/
        │
        ▼
  ┌─────────────────────────────────────┐
  │  Backup            (BackupRestore)  │  ← copies input to backup/<RUN_ID>/
  │  0 ─ Raw Validation (Validator)     │  ← checks columns, empty files
  │  1 ─ Transform      (DataTransformer)│  ← enrichment, calculations
  │  2 ─ Audit    (custom AuditProcessor)│  ← example custom processor
  │  3 ─ Delivery Dispatch (FileDispatcher)│ ← delivers by pattern
  └─────────────────────────────────────┘
        │
        ▼
  Parquet/CSV files in data/delivery/<RUN_ID>/
```

Each step is driven by a **YAML registry** file (in `config/registries/`) that declares *what* to do — the engine handles *how*. See [[Pipeline Configuration]] for how to customize the flow.

---

## Key Concepts at a Glance

- **Registry** — A YAML file that maps file-name patterns to rules (validators, transforms, or dispatch targets).
- **Processor** — A Python class that reads a registry and applies its rules to input files (`Validator`, `DataTransformer`, `FileDispatcher`, `BackupRestore`).
- **DataFacility** — A navigable Python object tree that mirrors `data_structure.yaml`, giving you `D.input`, `D.staging`, `D.static.mappings.product_mapping`, etc.
- **RUN_ID** — A timestamp (`YYYYMMDD_HHMMSS`) that isolates each pipeline execution into its own subfolder.

Start with [[Getting Started]] to set up your environment, or jump to [[Architecture Overview]] for the big picture.