"""File utility functions for handling uploads and processing."""

import os
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional, BinaryIO
import logging
from PIL import Image
import magic

from config import Config

logger = logging.getLogger(__name__)

def validate_file(file) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded file.

    Args:
        file: Streamlit uploaded file object

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file size
    if file.size > Config.MAX_UPLOAD_SIZE:
        return False, f"File size exceeds {Config.MAX_UPLOAD_SIZE_MB}MB limit"

    # Check file extension
    file_ext = Path(file.name).suffix.lower().replace('.', '')
    if file_ext not in Config.ALLOWED_EXTENSIONS:
        return False, f"File type '{file_ext}' not allowed. Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}"

    # Check MIME type for additional security
    try:
        file_bytes = file.read()
        file.seek(0)  # Reset file pointer

        mime = magic.from_buffer(file_bytes, mime=True)
        allowed_mimes = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg'
        }

        expected_mime = allowed_mimes.get(file_ext)
        if expected_mime and not mime.startswith(expected_mime.split('/')[0]):
            return False, f"File content doesn't match extension"

    except Exception as e:
        logger.warning(f"MIME type check failed: {e}")

    return True, None

def generate_unique_filename(original_filename: str) -> str:
    """
    Generate unique filename to prevent collisions.

    Args:
        original_filename: Original file name

    Returns:
        Unique filename
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_hash = hashlib.md5(f"{original_filename}_{timestamp}".encode()).hexdigest()[:8]
    extension = Path(original_filename).suffix

    return f"{timestamp}_{file_hash}{extension}"

def save_uploaded_file(file, subfolder: str = "receipts") -> str:
    """
    Save uploaded file to disk.

    Args:
        file: Streamlit uploaded file object
        subfolder: Subfolder within upload directory

    Returns:
        Path to saved file
    """
    try:
        # Create subfolder if needed
        upload_dir = Config.UPLOAD_FOLDER / subfolder
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        unique_filename = generate_unique_filename(file.name)
        file_path = upload_dir / unique_filename

        # Save file
        with open(file_path, 'wb') as f:
            f.write(file.getvalue())

        logger.info(f"File saved: {file_path}")
        return str(file_path)

    except Exception as e:
        logger.error(f"Failed to save file {file.name}: {e}")
        raise

def move_to_processed(file_path: str) -> str:
    """
    Move file to processed folder after successful processing.

    Args:
        file_path: Current file path

    Returns:
        New file path in processed folder
    """
    try:
        source = Path(file_path)
        processed_dir = Config.UPLOAD_FOLDER / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        destination = processed_dir / source.name

        # Handle duplicate names
        if destination.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            destination = processed_dir / f"{source.stem}_{timestamp}{source.suffix}"

        shutil.move(str(source), str(destination))
        logger.info(f"File moved to processed: {destination}")

        return str(destination)

    except Exception as e:
        logger.error(f"Failed to move file to processed: {e}")
        raise

def move_to_failed(file_path: str, error_msg: str = None) -> str:
    """
    Move file to failed folder after processing failure.

    Args:
        file_path: Current file path
        error_msg: Optional error message to save

    Returns:
        New file path in failed folder
    """
    try:
        source = Path(file_path)
        failed_dir = Config.UPLOAD_FOLDER / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)

        destination = failed_dir / source.name

        # Handle duplicate names
        if destination.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            destination = failed_dir / f"{source.stem}_{timestamp}{source.suffix}"

        shutil.move(str(source), str(destination))

        # Save error message if provided
        if error_msg:
            error_file = destination.with_suffix('.error.txt')
            with open(error_file, 'w') as f:
                f.write(f"Error processing {source.name}\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"Error: {error_msg}\n")

        logger.info(f"File moved to failed: {destination}")
        return str(destination)

    except Exception as e:
        logger.error(f"Failed to move file to failed: {e}")
        raise

def delete_file(file_path: str) -> bool:
    """
    Delete file from disk.

    Args:
        file_path: Path to file

    Returns:
        True if successful
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info(f"File deleted: {file_path}")
            return True
        return False

    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        return False

def get_file_info(file_path: str) -> dict:
    """
    Get file information.

    Args:
        file_path: Path to file

    Returns:
        Dictionary with file information
    """
    try:
        path = Path(file_path)

        if not path.exists():
            return None

        stats = path.stat()

        # Get image dimensions if it's an image
        dimensions = None
        if path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            try:
                with Image.open(path) as img:
                    dimensions = img.size
            except:
                pass

        return {
            'name': path.name,
            'path': str(path),
            'size': stats.st_size,
            'size_mb': round(stats.st_size / (1024 * 1024), 2),
            'extension': path.suffix.lower(),
            'created': datetime.fromtimestamp(stats.st_ctime),
            'modified': datetime.fromtimestamp(stats.st_mtime),
            'dimensions': dimensions
        }

    except Exception as e:
        logger.error(f"Failed to get file info for {file_path}: {e}")
        return None

def cleanup_old_files(days: int = 30):
    """
    Clean up old files from upload directories.

    Args:
        days: Delete files older than this many days
    """
    try:
        cutoff_time = datetime.now().timestamp() - (days * 86400)
        cleaned_count = 0

        for folder in ['receipts', 'processed', 'failed', 'temp']:
            folder_path = Config.UPLOAD_FOLDER / folder

            if not folder_path.exists():
                continue

            for file_path in folder_path.glob('*'):
                if file_path.is_file():
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"Deleted old file: {file_path}")

        logger.info(f"Cleanup completed. Deleted {cleaned_count} old files.")
        return cleaned_count

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 0

def create_thumbnail(image_path: str, size: Tuple[int, int] = (200, 200)) -> str:
    """
    Create thumbnail for image file.

    Args:
        image_path: Path to image file
        size: Thumbnail size (width, height)

    Returns:
        Path to thumbnail file
    """
    try:
        source = Path(image_path)
        thumb_dir = Config.UPLOAD_FOLDER / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        thumb_path = thumb_dir / f"thumb_{source.name}"

        with Image.open(source) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path)

        return str(thumb_path)

    except Exception as e:
        logger.error(f"Failed to create thumbnail for {image_path}: {e}")
        return None

def get_upload_statistics() -> dict:
    """
    Get statistics about uploaded files.

    Returns:
        Dictionary with upload statistics
    """
    try:
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'by_status': {},
            'by_extension': {},
            'recent_uploads': []
        }

        for folder in ['receipts', 'processed', 'failed']:
            folder_path = Config.UPLOAD_FOLDER / folder
            if not folder_path.exists():
                continue

            files = list(folder_path.glob('*'))
            stats['by_status'][folder] = len(files)

            for file_path in files:
                if file_path.is_file():
                    stats['total_files'] += 1
                    stats['total_size_mb'] += file_path.stat().st_size / (1024 * 1024)

                    ext = file_path.suffix.lower()
                    stats['by_extension'][ext] = stats['by_extension'].get(ext, 0) + 1

                    # Add to recent if within last 7 days
                    if file_path.stat().st_mtime > (datetime.now().timestamp() - 604800):
                        stats['recent_uploads'].append({
                            'name': file_path.name,
                            'folder': folder,
                            'size_mb': round(file_path.stat().st_size / (1024 * 1024), 2),
                            'date': datetime.fromtimestamp(file_path.stat().st_mtime)
                        })

        stats['total_size_mb'] = round(stats['total_size_mb'], 2)
        stats['recent_uploads'].sort(key=lambda x: x['date'], reverse=True)

        return stats

    except Exception as e:
        logger.error(f"Failed to get upload statistics: {e}")
        return {}