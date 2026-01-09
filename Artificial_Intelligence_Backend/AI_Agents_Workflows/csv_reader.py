"""
Custom CSV Reader for RAG with row-level chunking.
Creates one chunk per row with column headers for better semantic search.
"""
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional


class CSVRowReader:
    """
    Reads CSV files and chunks each row individually with column headers.
    This significantly improves RAG retrieval accuracy for tabular data.
    """
    
    def __init__(
        self,
        max_rows_per_chunk: int = 1,  # Default: 1 row per chunk for precise retrieval
        include_row_number: bool = True,
        delimiter: str = ",",
        encoding: str = "utf-8"
    ):
        """
        Initialize the CSV row reader.
        
        Args:
            max_rows_per_chunk: How many rows to combine in one chunk (1 = most precise)
            include_row_number: Whether to include row number in chunk metadata
            delimiter: CSV delimiter character
            encoding: File encoding
        """
        self.max_rows_per_chunk = max(1, max_rows_per_chunk)
        self.include_row_number = include_row_number
        self.delimiter = delimiter
        self.encoding = encoding
        
    def read(
        self,
        path: str | Path,
        user_id: Optional[str] = None,
        file_sha256: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Read a CSV file and return a list of document chunks (one per row or group of rows).
        
        Args:
            path: Path to the CSV file
            user_id: User ID for metadata
            file_sha256: SHA256 hash of the file for deduplication
            
        Returns:
            List of document dicts with 'content' and 'metadata' keys
        """
        path = Path(path)
        file_name = path.name
        documents = []
        
        try:
            with open(path, 'r', encoding=self.encoding, errors='replace') as f:
                # Try to detect delimiter if not standard comma
                sample = f.read(4096)
                f.seek(0)
                
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    reader = csv.DictReader(f, dialect=dialect)
                except csv.Error:
                    # Fall back to specified delimiter
                    reader = csv.DictReader(f, delimiter=self.delimiter)
                
                headers = reader.fieldnames
                if not headers:
                    logging.warning(f"CSV file {file_name} has no headers, skipping")
                    return []
                
                # Clean headers (remove BOM, strip whitespace)
                headers = [h.lstrip('\ufeff').strip() for h in headers]
                
                row_buffer = []
                row_numbers = []
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    row_buffer.append(row)
                    row_numbers.append(row_num)
                    
                    if len(row_buffer) >= self.max_rows_per_chunk:
                        chunk = self._create_chunk(
                            rows=row_buffer,
                            headers=headers,
                            row_numbers=row_numbers,
                            file_name=file_name,
                            path=path,
                            user_id=user_id,
                            file_sha256=file_sha256
                        )
                        if chunk:
                            documents.append(chunk)
                        row_buffer = []
                        row_numbers = []
                
                # Handle remaining rows
                if row_buffer:
                    chunk = self._create_chunk(
                        rows=row_buffer,
                        headers=headers,
                        row_numbers=row_numbers,
                        file_name=file_name,
                        path=path,
                        user_id=user_id,
                        file_sha256=file_sha256
                    )
                    if chunk:
                        documents.append(chunk)
                        
        except Exception as e:
            logging.error(f"Error reading CSV file {path}: {e}")
            return []
        
        logging.info(f"CSVRowReader extracted {len(documents)} row-chunks from {file_name}")
        return documents
    
    def _create_chunk(
        self,
        rows: List[Dict],
        headers: List[str],
        row_numbers: List[int],
        file_name: str,
        path: Path,
        user_id: Optional[str],
        file_sha256: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Create a document chunk from one or more rows."""
        if not rows:
            return None
            
        # Build content string with column headers for each row
        content_parts = []
        for row in rows:
            row_text = ", ".join([
                f"{header}: {row.get(header, '').strip()}"
                for header in headers
                if row.get(header, '').strip()  # Skip empty values
            ])
            if row_text:
                content_parts.append(row_text)
        
        if not content_parts:
            return None
            
        content = "\n".join(content_parts)
        
        # Build metadata
        meta = {
            "user_id": str(user_id) if user_id else None,
            "source_file": file_name,  # Only filename, not full path for privacy
            "filename": file_name,
            "file_sha256": file_sha256,
            "element_type": "csv_row",
            "row_numbers": row_numbers if self.include_row_number else None,
            "columns": headers
        }
        
        # Remove None values from metadata
        meta = {k: v for k, v in meta.items() if v is not None}
        
        return {
            "content": content,
            "metadata": meta
        }


def get_csv_row_reader(
    max_rows_per_chunk: int = 1,
    include_row_number: bool = True
) -> CSVRowReader:
    """
    Factory function to get a CSV row reader.
    
    Args:
        max_rows_per_chunk: Rows per chunk (1 = most precise for lookups)
        include_row_number: Include row numbers in metadata
        
    Returns:
        CSVRowReader instance
    """
    return CSVRowReader(
        max_rows_per_chunk=max_rows_per_chunk,
        include_row_number=include_row_number
    )


# For batch processing: group small rows to avoid too many tiny chunks
def get_csv_reader_for_large_files(estimated_rows: int = 1000) -> CSVRowReader:
    """
    Get optimized CSV reader based on estimated file size.
    
    For files with many rows, groups rows together to balance
    precision vs. chunk count.
    
    Args:
        estimated_rows: Estimated number of rows
        
    Returns:
        CSVRowReader with appropriate chunking
    """
    if estimated_rows < 100:
        # Small file: one row per chunk for maximum precision
        return CSVRowReader(max_rows_per_chunk=1)
    elif estimated_rows < 1000:
        # Medium file: 3-5 rows per chunk
        return CSVRowReader(max_rows_per_chunk=3)
    else:
        # Large file: 10 rows per chunk to manage vector DB size
        return CSVRowReader(max_rows_per_chunk=10)
