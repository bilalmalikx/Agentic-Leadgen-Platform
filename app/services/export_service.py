"""
Export Service
Export leads to CSV, JSON, Excel formats with async support
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime
import csv
import json
import io
import os
from pathlib import Path

from app.core.logging import get_logger
from app.core.config import settings
from app.models.lead import Lead

logger = get_logger(__name__)


class ExportService:
    """Service for exporting leads to various formats"""
    
    def __init__(self):
        self.export_dir = Path(settings.export_temp_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    async def export_leads(
        self,
        leads: List[Lead],
        format: str = "csv",
        fields: Optional[List[str]] = None,
        include_metadata: bool = False,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Export leads to specified format
        Returns file info and download URL
        """
        
        if format not in ["csv", "json", "excel"]:
            raise ValueError(f"Unsupported format: {format}")
        
        # Define default fields
        default_fields = [
            "email", "first_name", "last_name", "full_name", "company_name",
            "job_title", "location", "score", "quality", "status", "source",
            "created_at"
        ]
        export_fields = fields or default_fields
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"leads_export_{timestamp}.{format}"
        filepath = self.export_dir / filename
        
        # Export based on format
        if format == "csv":
            content = await self._export_to_csv(leads, export_fields, include_metadata)
            mime_type = "text/csv"
        elif format == "json":
            content = await self._export_to_json(leads, export_fields, include_metadata)
            mime_type = "application/json"
        elif format == "excel":
            content = await self._export_to_excel(leads, export_fields, include_metadata)
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Write file
        with open(filepath, "wb") as f:
            f.write(content)
        
        file_size = filepath.stat().st_size
        
        # Generate download URL (in production, this would be S3 URL)
        download_url = f"/api/v1/exports/download/{filename}"
        
        logger.info(f"Exported {len(leads)} leads to {format}, file size: {file_size} bytes")
        
        return {
            "filename": filename,
            "format": format,
            "file_size": file_size,
            "lead_count": len(leads),
            "download_url": download_url,
            "expires_in_hours": 24,
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def export_campaign_sync(
        self,
        campaign_id: UUID,
        format: str = "csv",
        user_id: Optional[UUID] = None
    ) -> str:
        """
        Synchronous export for Celery tasks
        Returns download URL
        """
        from app.db.session import get_sync_session
        from app.db.repositories.lead_repository import LeadRepository
        
        with get_sync_session() as db:
            repo = LeadRepository(db)
            leads, _ = repo.get_by_campaign(campaign_id, limit=settings.export_max_rows)
            
            result = await self.export_leads(
                leads=leads,
                format=format,
                user_id=user_id
            )
            
            return result["download_url"]
    
    async def _export_to_csv(
        self,
        leads: List[Lead],
        fields: List[str],
        include_metadata: bool = False
    ) -> bytes:
        """Export leads to CSV format"""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        
        for lead in leads:
            row = {}
            for field in fields:
                value = getattr(lead, field, None)
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, 'value'):  # Enum
                    value = value.value
                row[field] = value
            
            if include_metadata:
                row["metadata"] = json.dumps(lead.metadata)
                row["enriched_data"] = json.dumps(lead.enriched_data)
                row["raw_scraped_data"] = json.dumps(lead.raw_scraped_data)[:1000]
            
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')
    
    async def _export_to_json(
        self,
        leads: List[Lead],
        fields: List[str],
        include_metadata: bool = False
    ) -> bytes:
        """Export leads to JSON format"""
        
        data = []
        for lead in leads:
            lead_dict = {}
            for field in fields:
                value = getattr(lead, field, None)
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, 'value'):  # Enum
                    value = value.value
                lead_dict[field] = value
            
            if include_metadata:
                lead_dict["metadata"] = lead.metadata
                lead_dict["enriched_data"] = lead.enriched_data
                lead_dict["raw_scraped_data"] = lead.raw_scraped_data
            
            data.append(lead_dict)
        
        return json.dumps(data, indent=2, default=str).encode('utf-8')
    
    async def _export_to_excel(
        self,
        leads: List[Lead],
        fields: List[str],
        include_metadata: bool = False
    ) -> bytes:
        """Export leads to Excel format"""
        
        try:
            import pandas as pd
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            
            # Convert to DataFrame
            data = []
            for lead in leads:
                row = {}
                for field in fields:
                    value = getattr(lead, field, None)
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif hasattr(value, 'value'):  # Enum
                        value = value.value
                    row[field] = value
                
                if include_metadata:
                    row["metadata"] = str(lead.metadata)[:500]
                    row["enriched_data"] = str(lead.enriched_data)[:500]
                
                data.append(row)
            
            df = pd.DataFrame(data)
            
            # Create Excel file with styling
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Leads', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Leads']
                
                # Style header row
                header_font = Font(bold=True, color="FFFFFF")
                header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
                
                for cell in worksheet[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center")
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            return output.getvalue()
            
        except ImportError:
            logger.warning("pandas not installed, falling back to CSV")
            return await self._export_to_csv(leads, fields, include_metadata)
    
    async def get_export_file(self, filename: str) -> Optional[Tuple[bytes, str]]:
        """
        Get export file by filename
        Returns (file_content, mime_type) or None
        """
        filepath = self.export_dir / filename
        
        if not filepath.exists():
            return None
        
        # Determine mime type
        if filename.endswith('.csv'):
            mime_type = "text/csv"
        elif filename.endswith('.json'):
            mime_type = "application/json"
        elif filename.endswith('.xlsx'):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            mime_type = "application/octet-stream"
        
        with open(filepath, "rb") as f:
            content = f.read()
        
        return content, mime_type
    
    async def cleanup_old_exports(self, max_age_hours: int = 24):
        """
        Delete export files older than max_age_hours
        """
        now = datetime.utcnow()
        deleted_count = 0
        
        for filepath in self.export_dir.iterdir():
            if filepath.is_file():
                file_age = now - datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_age.total_seconds() > max_age_hours * 3600:
                    filepath.unlink()
                    deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old export files")
        
        return deleted_count
    
    async def get_export_stats(self) -> Dict[str, Any]:
        """
        Get statistics about exports
        """
        total_files = 0
        total_size = 0
        
        for filepath in self.export_dir.iterdir():
            if filepath.is_file():
                total_files += 1
                total_size += filepath.stat().st_size
        
        return {
            "total_exports": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "export_directory": str(self.export_dir),
            "max_age_hours": 24
        }