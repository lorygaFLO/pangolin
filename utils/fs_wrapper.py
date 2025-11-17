import fsspec
import os
from pathlib import Path

class FSWrapper:
    """Wrapper per fsspec che copre le principali operazioni su file e directory"""
    
    def __init__(self, protocol="file", **storage_options):
        """Inizializza il filesystem (es: 'file', 's3', 'gcs', ecc.)"""
        self.fs = fsspec.filesystem(protocol, **storage_options)
        self.protocol = protocol
    
    # Lettura/scrittura file
    def open(self, path, mode='r', **kwargs):
        """Apre un file"""
        return self.fs.open(path, mode, **kwargs)
    
    def read(self, path, mode='r'):
        """Legge il contenuto di un file"""
        with self.fs.open(path, mode) as f:
            return f.read()
    
    def write(self, path, data, mode='w'):
        """Scrive dati in un file"""
        with self.fs.open(path, mode) as f:
            f.write(data)
    
    # Copia/spostamento file
    def copy(self, src, dst):
        """Copia un file da src a dst"""
        self.fs.copy(src, dst)
    
    def move(self, src, dst):
        """Sposta un file da src a dst"""
        self.fs.move(src, dst)
    
    # Rimozione file/cartelle
    def remove(self, path):
        """Rimuove un file"""
        self.fs.rm(path, recursive=False)
    
    def rmtree(self, path):
        """Rimuove una directory e tutto il suo contenuto"""
        self.fs.rm(path, recursive=True)
    
    # Creazione directory
    def makedirs(self, path, exist_ok=True):
        """Crea una directory e tutte le directory intermedie"""
        self.fs.makedirs(path, exist_ok=exist_ok)
    
    def mkdir(self, path, exist_ok=False):
        """Crea una singola directory"""
        try:
            self.fs.mkdir(path)
        except FileExistsError:
            if not exist_ok:
                raise
    
    # Verifica esistenza
    def exists(self, path):
        """Verifica se un path esiste"""
        return self.fs.exists(path)
    
    def isfile(self, path):
        """Verifica se il path è un file"""
        return self.fs.isfile(path)
    
    def isdir(self, path):
        """Verifica se il path è una directory"""
        return self.fs.isdir(path)
    
    # Elenco file/cartelle
    def listdir(self, path):
        """Elenca file e cartelle in una directory"""
        return [os.path.basename(p) for p in self.fs.ls(path)]
    
    def glob(self, pattern):
        """Trova file che corrispondono a un pattern"""
        return self.fs.glob(pattern)
    
    # Path join
    def join(self, *paths):
        """Unisce componenti di path"""
        return os.path.join(*paths)
    
    # Estrazione nome file/cartella
    def basename(self, path):
        """Restituisce il nome del file o directory"""
        return os.path.basename(path)
    
    def dirname(self, path):
        """Restituisce la directory contenente il path"""
        return os.path.dirname(path)
    
    # Ottieni dimensione file
    def getsize(self, path):
        """Restituisce la dimensione del file in bytes"""
        return self.fs.size(path)
    
    # Path absolute/relative
    def abspath(self, path):
        """Restituisce il path assoluto"""
        if self.protocol == "file":
            return os.path.abspath(path)
        return path  # Per filesystem remoti, ritorna il path così com'è
    
    def relpath(self, path, start=None):
        """Restituisce il path relativo"""
        if self.protocol == "file":
            return os.path.relpath(path, start=start or os.getcwd())
        return path  # Per filesystem remoti, ritorna il path così com'è
    
    def splitext(self, path):
        return os.path.splitext(path)
    
    def isabs(self, path):
        """Verifica se il path è assoluto"""
        return os.path.isabs(path)


# Esempio di utilizzo
    # Esempio di utilizzo con S3 (richiede 's3fs' installato)
    # try:
    #     s3_fs = FSWrapper(protocol="s3", key="YOUR_AWS_ACCESS_KEY", secret="YOUR_AWS_SECRET_KEY")
    #     s3_bucket = "your-test-bucket"
    #     s3_file = s3_fs.join(s3_bucket, "test_s3.txt")
    #     s3_dir = s3_fs.join(s3_bucket, "test_s3_dir")

    #     s3_fs.makedirs(s3_dir, exist_ok=True)
    #     s3_fs.write(s3_file, "Hello from S3!")
    #     print(f"S3 file content: {s3_fs.read(s3_file)}")
    #     s3_fs.rmtree(s3_bucket) # Be careful with this in production!
    #     print(f"S3 test completed.")
    # except ImportError:
    #     print("s3fs not installed, skipping S3 test.")
    # except Exception as e:
    #     print(f"S3 test failed: {e}")

    # Esempio di utilizzo con Azure Blob Storage (richiede 'adlfs' installato)
    # try:
    #     azure_fs = FSWrapper(protocol="abfs", account_name="your_azure_account_name", account_key="your_azure_account_key")
    #     azure_container = "your-test-container"
    #     azure_file = azure_fs.join(azure_container, "test_azure.txt")
    #     azure_dir = azure_fs.join(azure_container, "test_azure_dir")

    #     azure_fs.makedirs(azure_dir, exist_ok=True)
    #     azure_fs.write(azure_file, "Hello from Azure Blob!")
    #     print(f"Azure file content: {azure_fs.read(azure_file)}")
    #     azure_fs.rmtree(azure_container) # Be careful with this in production


if __name__ == "__main__":
    # Crea wrapper per filesystem locale
    fs = FSWrapper(protocol="file")
    
    # Test delle funzionalità
    test_dir = "/tmp/fsspec_test"
    test_file = fs.join(test_dir, "test.txt")
    
    # Crea directory
    fs.makedirs(test_dir, exist_ok=True)
    print(f"Directory creata: {test_dir}")
    
    # Scrivi file
    fs.write(test_file, "Hello, fsspec wrapper!")
    print(f"File scritto: {test_file}")
    
    # Leggi file
    content = fs.read(test_file)
    print(f"Contenuto: {content}")
    
    # Verifica esistenza
    print(f"File exists: {fs.exists(test_file)}")
    print(f"Is file: {fs.isfile(test_file)}")
    print(f"Is dir: {fs.isdir(test_dir)}")
    
    # Dimensione file
    print(f"File size: {fs.getsize(test_file)} bytes")
    
    # Basename e dirname
    print(f"Basename: {fs.basename(test_file)}")
    print(f"Dirname: {fs.dirname(test_file)}")
    
    # Lista directory
    print(f"Files in dir: {fs.listdir(test_dir)}")
    
    # Pulizia
    fs.rmtree(test_dir)
    print(f"Directory rimossa: {test_dir}")