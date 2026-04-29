"""
DataFacility — Declarative, YAML-driven data access layer for Pangolin.
=========================================================================

DataFacility maps a YAML schema (``config/data_structure.yaml``) onto the
filesystem so that every file and folder in the project can be accessed as
a navigable Python object tree.  Path resolution, timestamping, versioning,
and multi-format I/O are handled transparently.


Quick-start
-----------

.. code-block:: python

    from engine.DataFacility import get_project_data

    D = get_project_data()          # loads config/data_structure.yaml
    print(D)                        # overview: base path, data path, RUN_ID


Browsing the tree
-----------------

Every top-level key in the YAML schema becomes an attribute of ``D``.
Nested keys become child attributes, forming a navigable tree:

.. code-block:: python

    D.input                         # <DataFolder: input>   → data/input/
    D.staging                       # <DataFolder: staging>  → data/staging/<RUN_ID>/
    D.delivery                      # <DataFolder: delivery> → data/delivery/<RUN_ID>/
    D.static                        # <DataFolder: static>   → data/static/
    D.static.mappings               # <DataFolder: mappings> → data/static/mappings/
    D.static.mappings.product_mapping   # <DataFile: product_mapping.csv>

    # DataNode.__repr__ shows existence status and size:
    #   <DataFile: product_mapping.csv [✓] 4.2KB>
    #     Path: C:\\...\\data\\static\\mappings\\product_mapping.csv


Inspecting a node
-----------------

.. code-block:: python

    node = D.static.mappings.product_mapping

    node.name            # 'product_mapping'
    node.is_file         # True
    node.path            # Path('…/data/static/mappings/product_mapping.csv')
    node.file_format     # 'csv'   (inferred from extension)
    node.description     # value of _description from YAML (str)
    node.exists()        # True / False
    node.config          # raw dict from YAML for this node

    # Folder nodes expose their children:
    D.delivery.children()           # {'sales_final': <DataNode>, 'sales_report': <DataNode>}
    D.delivery.list('*.csv')        # [Path(...), ...]  — glob the folder


Custom YAML attributes
~~~~~~~~~~~~~~~~~~~~~~

Any key starting with ``_`` that is not a reserved keyword
(``_filename``, ``_path``, ``_settings_key``, ``_timestamped``, ``_versioned``,
``_description``) is exposed as a Python attribute with the leading
underscore stripped:

.. code-block:: yaml

    # data_structure.yaml excerpt
    staging:
      0_validator:
        _pattern_matching: true

.. code-block:: python

    D.staging.0_validator is not accessible with dot notation (starts with
    a digit), but you can use ``get_node``:

    node = D.get_node("staging.0_validator")
    node.pattern_matching    # True   (originally _pattern_matching)
    node.list_attributes()   # {'pattern_matching': True}


Reading files
-------------

``DataNode.read()`` dispatches on the inferred format and honours the
backend engine configured in Settings (``BACKEND_ENGINE``).

.. code-block:: python

    # CSV  → polars.DataFrame (or pandas if BACKEND_ENGINE='pandas')
    df = D.static.mappings.product_mapping.read()

    # Override the default delimiter for this call only:
    df = D.static.mappings.product_mapping.read(delimiter=',')

    # Parquet
    df = D.delivery.sales_final.read()          # if it were .parquet

    # Excel
    report = D.delivery.sales_report.read()     # .xlsx → DataFrame

    # JSON / YAML → native Python dict / list
    data = D.cache.some_json_file.read()


Writing files
-------------

``DataNode.write()`` supports three modes: ``overwrite`` (default),
``append``, and ``update``.

.. code-block:: python

    import polars as pl

    df = pl.DataFrame({
        "product_id": ["A1", "B2"],
        "price": [9.99, 14.50],
    })

    # Overwrite (default) ------------------------------------------------
    D.delivery.sales_final.write(df)

    # Append — reads existing data, concatenates, writes back -------------
    D.delivery.sales_final.write(df, mode='append')
    # Shortcut:
    D.delivery.sales_final.append(df)

    # Update (JSON/YAML dicts only) — merges keys ------------------------
    D.cache.some_yaml.write({"new_key": 42}, mode='update')
    # Shortcut:
    D.cache.some_yaml.update({"new_key": 42})

    # Extra kwargs are forwarded to the underlying writer:
    D.delivery.sales_final.write(df, delimiter=',')


Versioning
~~~~~~~~~~

Nodes marked ``_versioned: true`` in the YAML schema automatically back
up the existing file into a ``history/`` subfolder (timestamped) before
an overwrite:

.. code-block:: yaml

    inventory_snapshot:
      _filename: "inventory_snapshot_product_ids.csv"
      _versioned: true

.. code-block:: python

    # First write — creates the file.
    D.static.mappings.inventory_snapshot.write(df)

    # Second write — moves the previous version to
    #   …/static/mappings/history/inventory_snapshot_20260218_231500.csv
    # then writes the new data.
    D.static.mappings.inventory_snapshot.write(new_df)


Deleting files
--------------

.. code-block:: python

    D.delivery.sales_final.delete()   # removes the file if it exists


Path resolution rules
---------------------

DataFacility resolves each node's filesystem path using the following
priority order:

1. **_settings_key** — the node's folder name is read from Settings at
   runtime.  The resolved path is ``DATAPATH / <settings_value>``.

   .. code-block:: yaml

       input:
         _settings_key: "INPUT_FOLDER_NAME"
       # With INPUT_FOLDER_NAME="input" → data/input/

2. **_path** — an explicit path relative to ``DATAPATH``.

   .. code-block:: yaml

       cache:
         _path: "cache"
       # → data/cache/

3. **Default** — folders use ``<parent_path>/<node_name>``, files use
   ``<parent_path>``.


Timestamped folders
~~~~~~~~~~~~~~~~~~~

When ``_timestamped: true`` is set (or inherited from a parent), the
current ``RUN_ID`` (e.g. ``20260218_215956``) is appended to the path:

.. code-block:: python

    D.staging.path        # data/staging/20260218_215956/
    D.delivery.path       # data/delivery/20260218_215956/

This ensures every pipeline run writes to an isolated directory.


Navigating by string path — ``get_node()``
-------------------------------------------

Useful when the path comes from a configuration registry (e.g. a
transformer/validator parameter stored as a string):

.. code-block:: python

    node = D.get_node("static.mappings.product_mapping")
    # Equivalent to D.static.mappings.product_mapping

    # The "D." prefix is tolerated and stripped automatically:
    node = D.get_node("D.static.mappings.product_mapping")

    if node.exists():
        df = node.read()


Switching between pipeline runs
--------------------------------

By default DataFacility uses the current ``RUN_ID`` from Settings.
You can temporarily switch to a previous run to read its outputs:

.. code-block:: python

    # List the 10 most recent runs
    D.list_runs()
    # ['20260217_190454', '20260217_192638', '20260218_215956', ...]

    # Switch to a specific run by ID
    D.switch_to_run("20260217_192638")
    old_df = D.delivery.sales_final.read()

    # Or use a negative index (-1 = previous run, -2 = two runs ago)
    D.switch_to_run(-1)

    # Restore the original (current) RUN_ID
    D.restore_current_run()

⚠ ``switch_to_run`` mutates the global Settings singleton.  Use
``restore_current_run`` when done to avoid side-effects on the rest of
the pipeline.


Validating required files
-------------------------

Nodes with ``_required: true`` can be bulk-checked:

.. code-block:: python

    results = D.validate_required()
    # {'static.mappings.product_mapping': True}

    missing = [path for path, ok in results.items() if not ok]
    if missing:
        raise FileNotFoundError(f"Required files missing: {missing}")


Listing folder contents
-----------------------

.. code-block:: python

    # All files in input/
    D.input.list()                  # [Path('…/FR_sales_data…csv'), ...]

    # Glob filtering
    D.input.list('FR_*.csv')        # only French files
    D.input.list('*.parquet')       # only parquet files

    # Staging sub-step folders (timestamped)
    D.staging.list()                # contents of data/staging/<RUN_ID>/


Full pipeline example
---------------------

.. code-block:: python

    from engine.DataFacility import get_project_data

    D = get_project_data()

    # 1. Check prerequisites
    results = D.validate_required()
    assert all(results.values()), f"Missing: {[k for k,v in results.items() if not v]}"

    # 2. Read input
    raw_files = D.input.list('*_sales_data_*.csv')
    for f in raw_files:
        print(f"Processing {f.name}")

    # 3. Read a static mapping
    mapping = D.static.mappings.product_mapping.read()

    # 4. Write processed output
    import polars as pl
    result = pl.DataFrame({"col": [1, 2, 3]})
    D.delivery.sales_final.write(result)

    # 5. Verify
    print(D.delivery.sales_final)
    #   <DataFile: sales_final.csv [✓] 0.1KB>
    #     Path: …/data/delivery/20260218_215956/sales_final.csv


Notes
-----
- ``DataFacility`` is **not** a singleton; call ``get_project_data()`` to
  obtain a fresh instance.  However, the underlying ``Settings`` object
  *is* a singleton, so all instances share the same ``RUN_ID`` and paths.
- The YAML schema is loaded once at construction.  If you change
  ``data_structure.yaml`` at runtime, create a new instance.
- I/O methods forward ``**kwargs`` to the underlying library
  (``polars.read_csv``, ``pandas.to_parquet``, etc.), so any library-
  specific option is available.
"""

from typing import Any, Optional, Dict, List, Union
from datetime import datetime
import yaml
import json
import polars as pl

from config.settings import get_settings
from utils.fs_wrapper import FSWrapper

S = get_settings()
_fs = FSWrapper(
    protocol=getattr(S, "FS_PROTOCOL", "file"),
    **getattr(S, "FS_OPTIONS", {})
)
_local_fs = FSWrapper(protocol="file")  # always local — for loading repo config files


class DataNode:
    """Nodo navigabile con supporto Settings integration."""
    
    def __init__(self, name: str, config: Dict, parent_path: str, d_root: 'DataFacility'):
        self.name = name
        self.config = config
        self.parent_path = parent_path
        self.d_root = d_root
        self.fs = _fs
        self._children = {}
        
        # Attributi standard
        self.is_file = '_filename' in config
        self.description = config.get('_description', '')
        
        # Esponi attributi custom
        for key, value in config.items():
            if key.startswith('_') and key not in ['_filename', '_description', '_path', '_settings_key', '_timestamped', '_versioned']:
                attr_name = key[1:]
                setattr(self, attr_name, value)
        
        if self.is_file:
            self.filename = config['_filename']
            self.file_format = self._infer_format(self.filename)
            self.path = self.fs.join(self._resolve_path(), self.filename)
        else:
            self.path = self._resolve_path()
            # Inizializza figli
            for key, value in config.items():
                if not key.startswith('_'):
                    # Passa il path corretto ai figli
                    self._children[key] = DataNode(key, value, self.path, d_root)
    
    def _infer_format(self, filename: str) -> str:
        """Inferisce formato dall'estensione."""
        ext = self.fs.suffix(filename).lower()
        format_map = {
            '.csv': 'csv',
            '.parquet': 'parquet',
            '.pq': 'parquet',
            '.xlsx': 'excel',
            '.xls': 'excel',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.txt': 'text',
        }
        return format_map.get(ext, 'unknown')
    
    def _resolve_path(self) -> str:
        """
        Risolve path con priorità:
        1. _settings_key: usa valore da Settings
        2. _path: usa path fisso
        3. default: usa parent_path per file, parent_path/name per folder
        """
        # NUOVO: Se c'è _settings_key, usa Settings
        if '_settings_key' in self.config:
            settings_key = self.config['_settings_key']
            
            if not hasattr(S, settings_key):
                raise ValueError(f"Settings key '{settings_key}' defined for node '{self.name}' not found in Settings.")
            
            folder_name = getattr(S, settings_key)
            base = self.fs.join(S.DATAPATH, str(folder_name))

        # Path esplicito
        elif '_path' in self.config:
            base = self.fs.join(S.DATAPATH, self.config['_path'])
        
        # Default: usa parent_path per file, parent_path/name per folder
        else:
            if self.is_file:
                base = self.parent_path
            else:
                base = self.fs.join(self.parent_path, self.name)
        
        # Gestione timestamping
        if self.config.get('_timestamped') or self._parent_is_timestamped():
            if S.RUN_ID not in str(base):
                base = self.fs.join(base, S.RUN_ID)
        
        return base
    
    def _parent_is_timestamped(self) -> bool:
        """Controlla se parent ha _timestamped: true."""
        # Risali la catena per vedere se un parent ha _timestamped
        parent_str = str(self.parent_path)
        # Se RUN_ID è già nel parent path, allora il parent è timestamped
        return S.RUN_ID in parent_str
    
    def __getattr__(self, key: str):
        if key.startswith('_') or key in self.__dict__:
            return object.__getattribute__(self, key)
        
        if key in self._children:
            return self._children[key]
        
        raise AttributeError(f"'{self.name}' has no child '{key}'. Available: {list(self._children.keys())}")
    
    def __repr__(self) -> str:
        if self.is_file:
            exists = self.fs.exists(self.path)
            status = "✓" if exists else "✗"
            size = f"{self.fs.getsize(self.path) / 1024:.1f}KB" if exists else "N/A"
            return f"<DataFile: {self.filename} [{status}] {size}>\n  Path: {self.path}"
        return f"<DataFolder: {self.name}>\n  Path: {self.path}"
    
    def get_attribute(self, attr_name: str, default: Any = None) -> Any:
        """Accedi attributo custom."""
        return getattr(self, attr_name, default)
    
    def list_attributes(self) -> Dict[str, Any]:
        """Lista attributi custom."""
        return {k[1:]: v for k, v in self.config.items() 
                if k.startswith('_') and k not in ['_filename', '_description', '_path', '_timestamped', '_versioned']}
    
    # FILE OPERATIONS
    
    def read(self, **kwargs):
        """Legge file."""
        if not self.is_file:
            raise ValueError(f"{self.name} is a folder")
        
        if not self.fs.exists(self.path):
            raise FileNotFoundError(f"File not found: {self.path}")
        
        if self.file_format == 'csv':
            delimiter = kwargs.pop('delimiter', S.CSV_DELIMITER)
            if self.fs.protocol == 'file':
                return pl.read_csv(self.path, separator=delimiter, **kwargs)
            else:
                with self.fs.open(self.path, 'rb') as fh:
                    return pl.read_csv(fh, separator=delimiter, **kwargs)
        
        elif self.file_format == 'parquet':
            if self.fs.protocol == 'file':
                return pl.read_parquet(self.path, **kwargs)
            else:
                with self.fs.open(self.path, 'rb') as fh:
                    return pl.read_parquet(fh, **kwargs)
        
        elif self.file_format == 'excel':
            if self.fs.protocol == 'file':
                return pl.read_excel(self.path, **kwargs)
            else:
                with self.fs.open(self.path, 'rb') as fh:
                    return pl.read_excel(fh, **kwargs)
        
        elif self.file_format == 'json':
            with self.fs.open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        elif self.file_format == 'yaml':
            with self.fs.open(self.path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        else:
            raise ValueError(f"Unsupported format: {self.file_format}")
    
    def write(self, data: Any, mode: str = 'overwrite', **kwargs):
        """Scrive file."""
        if not self.is_file:
            raise ValueError(f"{self.name} is a folder")
        
        parent_dir = self.fs.dirname(self.path)
        self.fs.makedirs(parent_dir, exist_ok=True)
        
        # Versioning se richiesto
        if self.config.get('_versioned') and self.fs.exists(self.path) and mode == 'overwrite':
            self._backup_version()
        
        # APPEND
        if mode == 'append':
            if self.file_format in ['csv', 'parquet', 'excel']:
                if self.fs.exists(self.path):
                    existing = self.read()
                    data = pl.concat([existing, data])
            elif self.file_format == 'json':
                if self.fs.exists(self.path):
                    existing = self.read()
                    if isinstance(existing, list):
                        data = existing + ([data] if not isinstance(data, list) else data)
        
        # UPDATE (solo dict)
        elif mode == 'update':
            if self.file_format in ['json', 'yaml']:
                if self.fs.exists(self.path):
                    existing = self.read()
                    if isinstance(existing, dict) and isinstance(data, dict):
                        existing.update(data)
                        data = existing
        
        # Scrittura effettiva
        if self.file_format == 'csv':
            delimiter = kwargs.pop('delimiter', S.CSV_DELIMITER)
            if self.fs.protocol == 'file':
                data.write_csv(self.path, separator=delimiter, **kwargs)
            else:
                with self.fs.open(self.path, 'wb') as fh:
                    data.write_csv(fh, separator=delimiter, **kwargs)
        
        elif self.file_format == 'parquet':
            if self.fs.protocol == 'file':
                data.write_parquet(self.path, **kwargs)
            else:
                with self.fs.open(self.path, 'wb') as fh:
                    data.write_parquet(fh, **kwargs)
        
        elif self.file_format == 'excel':
            if self.fs.protocol == 'file':
                data.write_excel(self.path, **kwargs)
            else:
                with self.fs.open(self.path, 'wb') as fh:
                    data.write_excel(fh, **kwargs)
        
        elif self.file_format == 'json':
            with self.fs.open(self.path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif self.file_format == 'yaml':
            with self.fs.open(self.path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False)
    
    def append(self, data: Any, **kwargs):
        self.write(data, mode='append', **kwargs)
    
    def update(self, data: Dict, **kwargs):
        self.write(data, mode='update', **kwargs)
    
    def exists(self) -> bool:
        return self.fs.exists(self.path)
    
    def delete(self):
        if self.fs.exists(self.path):
            self.fs.remove(self.path)
    
    def _backup_version(self):
        """Crea backup versionato."""
        history_path = self.fs.join(self.fs.dirname(self.path), 'history')
        self.fs.makedirs(history_path, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stem = self.fs.stem(self.path)
        ext = self.fs.suffix(self.path)
        backup_name = f"{stem}_{timestamp}{ext}"
        self.fs.copy(self.path, self.fs.join(history_path, backup_name))
    
    def list(self, pattern: str = '*') -> List[str]:
        """Lista file in cartella."""
        if self.is_file:
            raise ValueError(f"{self.name} is a file")
        glob_pattern = self.fs.join(self.path, pattern)
        return self.fs.glob(glob_pattern)
    
    def children(self) -> Dict[str, 'DataNode']:
        return self._children


class DataFacility:
    """
    Facility D per navigazione struttura dati.
    
    RUN_ID viene da Settings, non serve initialize_run().
    """
    
    def __init__(self, structure_file: str = 'config/data_structure.yaml'):  # Use forward slash
        self.base_path = S.BASEPATH
        self.data_path = S.DATAPATH
        self.run_id = S.RUN_ID  # Usa RUN_ID da Settings
        self.fs = _fs
        
        # Carica schema — always from local filesystem (config lives in the repo)
        structure_path = _local_fs.join(self.base_path, structure_file)
        if not _local_fs.exists(structure_path):
            raise FileNotFoundError(f"Data structure file not found: {structure_path}")
        
        with _local_fs.open(structure_path, 'r', encoding='utf-8') as f:
            self.schema = yaml.safe_load(f)
        
        # Inizializza root nodes
        self._nodes = {}
        for key, config in self.schema.items():
            if not key.startswith('_'):
                self._nodes[key] = DataNode(key, config, self.data_path, self)
    
    def __getattr__(self, key: str) -> DataNode:
        if key.startswith('_') or key in self.__dict__:
            return object.__getattribute__(self, key)
        
        if key in self._nodes:
            return self._nodes[key]
        
        raise AttributeError(f"No data node '{key}'. Available: {list(self._nodes.keys())}")
    
    def __repr__(self) -> str:
        return f"<DataFacility>\n  Base: {self.base_path}\n  Data: {self.data_path}\n  RUN_ID: {self.run_id}"
    
    def switch_to_run(self, run_ref: Union[str, int]) -> str:
        """
        Cambia RUN_ID per accedere a run diverse.
        
        Args:
            run_ref:
                - String: run_id specifico
                - Int negativo: -1 = precedente, -2 = due run fa
        
        Returns:
            run_id selezionato
        """
        runs_path = self.fs.join(self.data_path, 'runs')
        if not self.fs.exists(runs_path):
            raise ValueError("No runs directory found")
        
        # Lista run disponibili
        entries = self.fs.listdir(runs_path)
        available_runs = sorted([
            e for e in entries
            if self.fs.isdir(self.fs.join(runs_path, e))
        ])
        
        if isinstance(run_ref, int):
            if run_ref >= 0:
                raise ValueError("Use negative integers. -1 = previous run")
            
            # Trova posizione run corrente
            try:
                current_idx = available_runs.index(self.run_id)
            except ValueError:
                current_idx = len(available_runs)  # Se run corrente non esiste ancora
            
            # Calcola indice target
            target_idx = current_idx + run_ref
            
            if target_idx < 0 or target_idx >= len(available_runs):
                raise ValueError(f"Run index out of range. Available: {len(available_runs)} runs")
            
            run_id = available_runs[target_idx]
        
        else:
            # Run specifica
            run_id = run_ref
            if run_id not in available_runs:
                raise ValueError(f"Run not found: {run_id}")
        
        # Cambia RUN_ID in Settings (temporaneamente)
        # Nota: questo modifica il singleton, usare con cautela
        old_run_id = S.RUN_ID
        S.RUN_ID = run_id
        
        # Ricrea i nodi con nuovo RUN_ID
        self.__init__(structure_file='config/data_structure.yaml')  # Use forward slash
        
        return run_id
    
    def restore_current_run(self):
        """Ripristina RUN_ID originale."""
        # Ripristina da Settings originale
        S_fresh = get_settings()
        S.RUN_ID = S_fresh.RUN_ID
        self.__init__(structure_file='config/data_structure.yaml')  # Use forward slash
    
    def list_runs(self, limit: int = 10) -> List[str]:
        """Lista run disponibili."""
        runs_path = self.fs.join(self.data_path, 'runs')
        if not self.fs.exists(runs_path):
            return []
        entries = self.fs.listdir(runs_path)
        runs = sorted([
            e for e in entries
            if self.fs.isdir(self.fs.join(runs_path, e))
        ])
        return runs[-limit:]
    
    def get_node(self, path: str) -> DataNode:
        """
        Gets a DataNode from a string path.
        Needed to pass a data structure like path in trasformers/validators parameters.
        
        Args:
            path: string like "static.mapping.product_mapping" or "D.static.mapping.product_mapping"
        
        Returns:
            DataNode object on which you can call .read(), .exists(), etc.
        
        Example:
            D = DataFacility()
            node = D.get_node("static.mapping.product_mapping")
            if node.exists():
                data = node.read()
        """
        # Remove "D." if present at the beginning
        if path.startswith("D."):
            path = path[2:]
        
        # Navigate the path
        node = self
        for part in path.split('.'):
            node = getattr(node, part)
        
        return node
    
    def validate_required(self) -> Dict[str, bool]:
        """Valida file required."""
        results = {}
        
        def check_node(node: DataNode, path: str = ""):
            current_path = f"{path}.{node.name}" if path else node.name
            
            if node.is_file and node.config.get('_required'):
                results[current_path] = node.exists()
            
            for child in node.children().values():
                check_node(child, current_path)
        
        for node in self._nodes.values():
            check_node(node)
        
        return results


def get_project_data(structure_file: str = 'config/data_structure.yaml') -> DataFacility:  # Use forward slash
    """Factory function."""
    return DataFacility(structure_file)

 