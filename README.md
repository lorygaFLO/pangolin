<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo_pangolin_dark.jpg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/logo_pangolin.jpg">
    <img src="docs/assets/logo_pangolin.jpg" alt="Pangolin logo" style="width: 200px; aspect-ratio: 1; object-fit: cover; border-radius: 15px;"/>
  </picture>
</p>

# Pangolin — Data Ingestion, Validation & Transformation Pipeline

Pangolin is a flexible, modular data processing pipeline built on top of **Prefect** and **Polars**. It automates multi-stage ingestion, validation, transformation, and delivery of data files, ensuring data quality and compliance with user-defined rules at every step.

It is designed to be easy to ship and quick to set up, making it a good fit for personal projects or small/medium enterprise pipelines. If you routinely process and validate data from third-party sources, Pangolin gives you a declarative, YAML-driven approach to defining pipeline stages — no core code changes needed.

## Key Features

* **Prefect-orchestrated pipeline** with full observability and retry support
* **Declarative YAML registries** — define validation, transformation, and routing rules without writing Python
* **Polars backend** — fast, memory-efficient dataframe processing
* **fsspec integration** — swap local storage for S3, GCS, or Azure with a one-line config change
* **DataFacility** — YAML-driven data access layer mapping folder structure into a navigable Python object tree
* **Per-stage HTML reports** generated automatically for every processed file
* **Non-destructive processing** — input files are never modified; each stage writes to its own staging folder
* **Extensible with decorators** — add validators/transformers with `@register_validator` / `@register_transformer`

## Project Structure

```
├── main.py                          # Pipeline entry point (Prefect flows)
├── example.env                      # Environment variable template
├── pyproject.toml                   # Project metadata & dependencies
├── config/
│   ├── settings.py                  # Settings loader (reads .env, builds paths)
│   ├── constants.py                 # System-wide constants
│   ├── data_structure.yaml          # Declarative folder/file schema (DataFacility)
│   └── registries/                  # YAML-driven stage configuration
│       ├── 0_raw_validation.yaml
│       ├── 1_dispatcher.yaml
│       ├── 2_transform_registry.yaml
│       ├── 3_validation.yaml
│       ├── 4_cross_validation.yaml
│       └── 5_dispatcher.yaml
├── engine/
│   ├── DataFacility.py              # YAML-driven data access layer
│   ├── reporter.py                  # Report generation
│   ├── core/
│   │   ├── exceptions.py            # Custom pipeline exceptions
│   │   └── logger.py                # Per-processor logger
│   └── processors/
│       ├── BaseProcessor.py         # Shared processor base class
│       ├── DataValidator.py         # Validation processor
│       ├── DataTranformer.py        # Transformation processor
│       └── FileDispatcher.py        # File routing processor
├── utils/
│   ├── validators.py                # Built-in validator functions
│   ├── transformers.py              # Built-in transformer functions
│   └── fs_wrapper.py                # fsspec filesystem wrapper
├── docker/
│   └── deploy.py                    # Prefect deployment script
├── data/
│   ├── input/                       # Drop input files here
│   ├── staging/                     # Per-run intermediate data
│   ├── delivery/                    # Final outputs (timestamped)
│   └── reports/                     # Pipeline reports (timestamped)
└── docs/
    └── doumentation-obsidian/       # Full documentation (Obsidian vault)
```

## Quick Start

```bash
pip install -e .
```

1. Copy `example.env` to `.env` and fill in the values
2. Place input files in `data/input/`
3. Run the pipeline:

```bash
python main.py
```

## Documentation

Full documentation is available in the [`docs/doumentation-obsidian/`](docs/doumentation-obsidian/) folder. It is structured as an [Obsidian](https://obsidian.md/) vault — open the folder in Obsidian for the best reading experience (linked pages, graph view, etc.).

| Guide | Description |
|-------|-------------|
| [Welcome](docs/documentation-obsidian/Welcome.md) | Introduction and overview |
| [Getting Started](docs/documentation-obsidian/Getting%20Started.md) | Installation, configuration, and first run |
| [Architecture Overview](docs/documentation-obsidian/Architecture%20Overview.md) | Pipeline stages, directory structure, and data flow |
| [Pipeline Configuration](docs/documentation-obsidian/Pipeline%20Configuration.md) | Registry files and YAML-driven stage configuration |
| [Registry Reference](docs/documentation-obsidian/Registry%20Reference.md) | Detailed reference for all registry formats |
| [Data Structure & DataFacility](docs/documentation-obsidian/Data%20Structure%20&%20DataFacility.md) | YAML-driven filesystem mapping |
| [Writing Validators](docs/documentation-obsidian/Writing%20Validators.md) | How to create custom validation functions |
| [Writing Transformers](docs/documentation-obsidian/Writing%20Transformers.md) | How to create custom transformation functions |
| [Creating a New Processor](docs/documentation-obsidian/Creating%20a%20New%20Processor.md) | Extending the engine with new processor types |

## Contributing

Contributions are welcome! Priority areas:

* **Dockerization** *(in progress)*
* **Full Prefect Integration** (deployment manifests, work pools, artifacts, notifications)
* **New File Format Support** (Excel, JSON, etc.)
* **Additional Validators/Transformers**
* **Cloud Storage** (S3/GCS/Azure documentation and examples)

