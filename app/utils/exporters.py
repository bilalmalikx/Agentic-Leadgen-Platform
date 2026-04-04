"""
Exporters
Export data to CSV, JSON, Excel formats
"""

from typing import List, Dict, Any, Optional, IO
import csv
import json
import io
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


class CSVExporter:
    """Export data to CSV format"""
    
    @staticmethod
    def export(data: List[Dict[str, Any]], fields: Optional[List[str]] = None) -> str:
        """
        Export list of dictionaries to CSV string
        """
        if not data:
            return ""
        
        if not fields:
            fields = list(data[0].keys())
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        
        for row in data:
            # Prepare row with only specified fields
            filtered_row = {field: row.get(field, "") for field in fields}
            writer.writerow(filtered_row)
        
        return output.getvalue()
    
    @staticmethod
    def export_to_file(data: List[Dict[str, Any]], filepath: str, fields: Optional[List[str]] = None) -> bool:
        """Export data to CSV file"""
        try:
            csv_content = CSVExporter.export(data, fields)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(csv_content)
            return True
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            return False


class JSONExporter:
    """Export data to JSON format"""
    
    @staticmethod
    def export(data: Any, indent: int = 2, default_str: bool = True) -> str:
        """
        Export data to JSON string
        """
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, 'dict'):
                return obj.dict()
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            return str(obj) if default_str else None
        
        return json.dumps(data, default=json_serializer, indent=indent)
    
    @staticmethod
    def export_to_file(data: Any, filepath: str, indent: int = 2) -> bool:
        """Export data to JSON file"""
        try:
            json_content = JSONExporter.export(data, indent)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_content)
            return True
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            return False


class ExcelExporter:
    """Export data to Excel format"""
    
    @staticmethod
    def export(data: List[Dict[str, Any]], sheet_name: str = "Sheet1") -> bytes:
        """
        Export list of dictionaries to Excel bytes
        """
        try:
            import pandas as pd
            from io import BytesIO
            
            df = pd.DataFrame(data)
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            return output.getvalue()
            
        except ImportError:
            logger.warning("pandas not installed, falling back to CSV")
            return CSVExporter.export(data).encode()
    
    @staticmethod
    def export_to_file(data: List[Dict[str, Any]], filepath: str, sheet_name: str = "Sheet1") -> bool:
        """Export data to Excel file"""
        try:
            excel_bytes = ExcelExporter.export(data, sheet_name)
            with open(filepath, 'wb') as f:
                f.write(excel_bytes)
            return True
        except Exception as e:
            logger.error(f"Failed to export Excel: {e}")
            return False


def export_data(data: List[Dict[str, Any]], format: str = "csv", **kwargs) -> str:
    """
    Export data to specified format
    """
    if format == "csv":
        return CSVExporter.export(data, kwargs.get("fields"))
    elif format == "json":
        return JSONExporter.export(data, kwargs.get("indent", 2))
    else:
        raise ValueError(f"Unsupported format: {format}")