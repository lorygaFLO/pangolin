<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo_pangolin_dark.jpg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/logo_pangolin.jpg">
    <img src="docs/assets/logo_pangolin.jpg" alt="Pangolin logo" style="width: 200px; aspect-ratio: 1; object-fit: cover; border-radius: 15px;"/>
  </picture>
</p>

# Pangolin — Battle-Ready Data Pipeline with Built-in Orchestration

**Pangolin** is a production-ready, modular data processing pipeline shipped with **Prefect** as its orchestrator and **Polars** as its dataframe engine. It gives you a complete, deployable system out of the box — with a pipeline infrastructure ready to run.

The current implementation targets a **data preboarding** use case: inspecting incoming data from third-party sources, applying validation rules, transforming values, and delivering clean, compliant datasets. However, the underlying architecture is generic and reusable — you can build entirely different workflows on top of the same structure for any project that involves staged data processing.



## Key Features

* **Prefect-orchestrated pipeline** with full observability and retry support
* **Declarative YAML registries** — define validation, transformation, and routing rules without writing Python
* **Polars backend** — fast, memory-efficient dataframe processing
* **fsspec integration** — swap local storage for S3, GCS, or Azure with a one-line config change
* **DataFacility** — YAML-driven data access layer mapping folder structure into a navigable Python object tree
* **Non-destructive processing** — input files are never modified; each stage writes to its own staging folder
* **Extensible with decorators** — add validators/transformers with `@register_validator` / `@register_transformer`

## Project Structure

```
├── main.py                    # Pipeline entry point (Prefect flows)
├── config/
│   ├── settings.py            # Settings loader
│   ├── data_structure.yaml    # Declarative folder/file schema
│   └── registries/            # YAML-driven stage configuration
├── engine/
│   ├── DataFacility.py        # YAML-driven data access layer
│   ├── reporter.py            # Report generation
│   ├── core/                  # Exceptions, logging
│   └── processors/            # BaseProcessor, Validator, Transformer, Dispatcher
├── utils/                     # Built-in validators, transformers, fs wrapper
├── docker/                    # Deployment scripts
├── data/                      # input / staging / delivery / reports
└── docs/                      # Documentation (Obsidian vault)
```

## Documentation

Full documentation lives in the [`docs/doumentation-obsidian/`](docs/doumentation-obsidian/) folder. It is structured as an [Obsidian](https://obsidian.md/) vault — open it in Obsidian for the best experience (linked pages, graph view, backlinks). Getting started instructions, architecture details, and guides for extending the pipeline are all included there.

## Contributing

If you run into any problem, feel free to open an issue — feedback and bug reports are always welcome.

The documentation includes a dedicated **Future Developments** section outlining planned improvements and ideas. Contributions are welcome! Priority areas:

* **Dockerization** *(in progress)*
* **Full Prefect Integration** (deployment manifests, work pools, artifacts, notifications)
* **New File Format Support** (Excel, JSON, etc.)
* **Additional Validators/Transformers**
* **Cloud Storage** (S3/GCS/Azure documentation and examples)

