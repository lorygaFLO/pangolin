from pathlib import Path
from typing import Any, Optional, Dict, List, Union
from datetime import datetime
import yaml
import json
import shutil
import polars as pl
import pandas as pd

from config.settings import get_settings
S = get_settings()


class DataNode:
    """Nodo navigabile con supporto Settings integration."""
    
    def __init__(self, name: str, config: Dict, parent_path: Path, d_root: 'DataFacility'):
        self.name = name
        self.config = config
        self.parent_path = parent_path
        self.d_root = d_root
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
            self.path = self._resolve_path() / self.filename
        else:
            self.path = self._resolve_path()
            # Inizializza figli
            for key, value in config.items():
                if not key.startswith('_'):
                    # Passa il path corretto ai figli
                    self._children[key] = DataNode(key, value, self.path, d_root)
    
    def _infer_format(self, filename: str) -> str:
        """Inferisce formato dall'estensione."""
        ext = Path(filename).suffix.lower()
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
    
    def _resolve_path(self) -> Path:
        """
        Risolve path con priorità:
        1. _settings_key: usa valore da Settings
        2. _path: usa path fisso
        3. default: usa parent_path per file, parent_path/name per folder
        """
        # NUOVO: Se c'è _settings_key, usa Settings
        if '_settings_key' in self.config:
            settings_key = self.config['_settings_key']
            
            # Ottieni valore da Settings
            if hasattr(S, settings_key):
                folder_name = getattr(S, settings_key)
                base = S.DATAPATH / folder_name  # S.DATAPATH is already a Path
            elif hasattr(S, f'PATH_{settings_key}'):
                # Prova anche PATH_INPUT, PATH_STAGING, etc
                base = getattr(S, f'PATH_{settings_key}')  # Already a Path
            else:
                raise ValueError(f"Settings key '{settings_key}' not found in Settings")
        
        # Path esplicito
        elif '_path' in self.config:
            base = S.DATAPATH / self.config['_path']  # S.DATAPATH is already a Path
        
        # Default: usa parent_path per file, parent_path/name per folder
        else:
            if self.is_file:
                base = self.parent_path
            else:
                base = self.parent_path / self.name
        
        # Gestione timestamping
        if self.config.get('_timestamped') or self._parent_is_timestamped():
            if S.RUN_ID not in str(base):
                base = base / S.RUN_ID
        
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
            status = "✓" if self.path.exists() else "✗"
            size = f"{self.path.stat().st_size / 1024:.1f}KB" if self.path.exists() else "N/A"
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
        
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        
        backend = S.BACKEND_ENGINE
        
        if self.file_format == 'csv':
            delimiter = kwargs.get('delimiter', S.CSV_DELIMITER)
            if backend == 'polars':
                return pl.read_csv(self.path, separator=delimiter, **kwargs)
            else:
                return pd.read_csv(self.path, sep=delimiter, **kwargs)
        
        elif self.file_format == 'parquet':
            if backend == 'polars':
                return pl.read_parquet(self.path, **kwargs)
            else:
                return pd.read_parquet(self.path, **kwargs)
        
        elif self.file_format == 'excel':
            if backend == 'polars':
                return pl.read_excel(self.path, **kwargs)
            else:
                return pd.read_excel(self.path, **kwargs)
        
        elif self.file_format == 'json':
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        elif self.file_format == 'yaml':
            with open(self.path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        else:
            raise ValueError(f"Unsupported format: {self.file_format}")
    
    def write(self, data: Any, mode: str = 'overwrite', **kwargs):
        """Scrive file."""
        if not self.is_file:
            raise ValueError(f"{self.name} is a folder")
        
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Versioning se richiesto
        if self.config.get('_versioned') and self.path.exists() and mode == 'overwrite':
            self._backup_version()
        
        # APPEND
        if mode == 'append':
            if self.file_format in ['csv', 'parquet', 'excel']:
                if self.path.exists():
                    existing = self.read()
                    if isinstance(data, pl.DataFrame):
                        data = pl.concat([existing, data])
                    else:
                        data = pd.concat([existing, data], ignore_index=True)
            elif self.file_format == 'json':
                if self.path.exists():
                    existing = self.read()
                    if isinstance(existing, list):
                        data = existing + ([data] if not isinstance(data, list) else data)
        
        # UPDATE (solo dict)
        elif mode == 'update':
            if self.file_format in ['json', 'yaml']:
                if self.path.exists():
                    existing = self.read()
                    if isinstance(existing, dict) and isinstance(data, dict):
                        existing.update(data)
                        data = existing
        
        # Scrittura effettiva
        if self.file_format == 'csv':
            delimiter = kwargs.get('delimiter', S.CSV_DELIMITER)
            if isinstance(data, pl.DataFrame):
                data.write_csv(self.path, separator=delimiter, **kwargs)
            else:
                data.to_csv(self.path, sep=delimiter, index=False, **kwargs)
        
        elif self.file_format == 'parquet':
            if isinstance(data, pl.DataFrame):
                data.write_parquet(self.path, **kwargs)
            else:
                data.to_parquet(self.path, index=False, **kwargs)
        
        elif self.file_format == 'excel':
            if isinstance(data, pl.DataFrame):
                data.write_excel(self.path, **kwargs)
            else:
                data.to_excel(self.path, index=False, **kwargs)
        
        elif self.file_format == 'json':
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif self.file_format == 'yaml':
            with open(self.path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False)
    
    def append(self, data: Any, **kwargs):
        self.write(data, mode='append', **kwargs)
    
    def update(self, data: Dict, **kwargs):
        self.write(data, mode='update', **kwargs)
    
    def exists(self) -> bool:
        return self.path.exists()
    
    def delete(self):
        if self.path.exists():
            self.path.unlink()
    
    def _backup_version(self):
        """Crea backup versionato."""
        history_path = self.path.parent / 'history'
        history_path.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{self.path.stem}_{timestamp}{self.path.suffix}"
        shutil.copy2(self.path, history_path / backup_name)
    
    def list(self, pattern: str = '*') -> List[Path]:
        """Lista file in cartella."""
        if self.is_file:
            raise ValueError(f"{self.name} is a file")
        return list(self.path.glob(pattern))
    
    def children(self) -> Dict[str, 'DataNode']:
        return self._children


class DataFacility:
    """
    Facility D per navigazione struttura dati.
    
    RUN_ID viene da Settings, non serve initialize_run().
    """
    
    def __init__(self, structure_file: str = 'config/data_structure.yaml'):  # Use forward slash
        self.base_path = S.BASEPATH  # Already a Path from Settings
        self.data_path = S.DATAPATH  # Already a Path from Settings
        self.run_id = S.RUN_ID  # Usa RUN_ID da Settings
        
        # Carica schema
        structure_path = self.base_path / structure_file
        if not structure_path.exists():
            raise FileNotFoundError(f"Data structure file not found: {structure_path}")
        
        with open(structure_path, 'r', encoding='utf-8') as f:
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
        runs_path = self.data_path / 'runs'
        if not runs_path.exists():
            raise ValueError("No runs directory found")
        
        # Lista run disponibili
        available_runs = sorted([d.name for d in runs_path.iterdir() if d.is_dir()])
        
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
        runs_path = self.data_path / 'runs'
        if not runs_path.exists():
            return []
        runs = sorted([d.name for d in runs_path.iterdir() if d.is_dir()])
        return runs[-limit:]
    
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