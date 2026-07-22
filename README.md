<p align="center">
  <img src="docs/assets/logo_pangolin_rounded.png" alt="Pangolin logo" width="200" height="200"/>
</p>

# Pangolin — Data Pipeline Template with Built-in Orchestration

**Pangolin** is a battle-ready, modular data processing pipeline shipped with **Prefect** as its orchestrator and **Polars** as its dataframe engine. It gives you a complete, deployable system out of the box — with a minimal pipeline infrastructure ready to run.

Pangolin started as a simple data validation tool. Solving one problem at a time, it gradually grew into something more structured — a framework that gives data specialists a solid foundation to build on, instead of ending up buried in messy, hard-to-maintain scripts.

The current implementation targets a **data preboarding** use case: inspecting incoming data from third-party sources, applying validation rules, transforming values, and delivering clean, compliant datasets. However, the underlying architecture is generic and reusable — you can build entirely different workflows on top of the same structure for any project that involves staged data processing.

The project supports multiple deployment modes: you can run it **locally**, deploy it on an **on-premise server**, or containerize it via **Docker** and point it at cloud storage — in all cases triggering pipeline runs directly from the **Prefect UI**. That said, Pangolin is currently scoped for **small enterprise applications** and has not yet been extensively tested in larger or more demanding environments. Use it accordingly.

## Key Features

* **Prefect-orchestrated pipeline** with full observability and retry support
* **Declarative YAML registries** — define validation, transformation, and routing rules without writing Python
* **Polars backend** — fast, memory-efficient dataframe processing
* **fsspec integration** — swap local storage for S3, GCS, or Azure with a one-line config change
* **DataFacility** — YAML-driven data access layer mapping folder structure into a navigable Python object tree
* **Extensible with decorators** — add custom validators/transformers with `@register_validator` / `@register_transformer`

## Project Structure

```
├── main.py                    # Pipeline entry point (Prefect flows)
├── config/
│   ├── settings.py            # Settings loader
│   ├── run_context.py         # Runtime context object
│   ├── data_structure.yaml    # Declarative folder/file schema
│   └── registries/            # YAML-driven stage configuration
├── engine/
│   ├── DataFacility.py        # YAML-driven data access layer
│   ├── reporter.py            # Report generation
│   ├── common/                # Exceptions, logging
│   └── processors/            # BaseProcessor, Validator, Transformer, Dispatcher, BackupRestore
├── utils/                     # Built-in validators, transformers, fs wrapper
├── docker/                    # Deployment scripts
├── data/                      # input / staging / delivery / backup / reports
├── test_files_generator/      # Synthetic input data generator
└── docs/                      # Documentation (Obsidian vault)
```

## Documentation

Full documentation lives in the [`docs/documentation-obsidian/`](docs/doumentation-obsidian/) folder. It is structured as an [Obsidian](https://obsidian.md/) vault — open it in Obsidian for the best experience (linked pages, graph view, backlinks). Getting started instructions, architecture details, and guides for extending the pipeline are all included there.

## Contributing

If you run into any problem, feel free to open an issue — feedback and bug reports are always welcome.

The documentation includes a dedicated **Future Developments** section outlining planned improvements and ideas. Contributions are welcome! Priority areas:

* **Better Dockerization**
* **Full Prefect Integration** (deployment manifests, work pools, artifacts, notifications)
* **New File Format Support** (Excel, JSON, etc.)
* **Additional Validators/Transformers**
* **Cloud Storage** (S3/GCS/Azure documentation and examples)


