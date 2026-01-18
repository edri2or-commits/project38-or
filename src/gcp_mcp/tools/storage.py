"""
Cloud Storage tools.

Provides bucket and object management capabilities.
"""

from typing import Optional

try:
    from google.cloud import storage

    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False


async def list_storage(
    bucket_name: Optional[str] = None, prefix: Optional[str] = None
) -> dict:
    """
    List Cloud Storage buckets or objects.

    Args:
        bucket_name: Bucket name (lists all buckets if None)
        prefix: Object prefix filter

    Returns:
        dict with list of buckets or objects
    """
    if not STORAGE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-storage not installed",
        }

    try:
        client = storage.Client()

        if bucket_name is None:
            # List all buckets
            buckets = []
            for bucket in client.list_buckets():
                buckets.append(
                    {
                        "name": bucket.name,
                        "location": bucket.location,
                        "storage_class": bucket.storage_class,
                        "created": str(bucket.time_created),
                    }
                )

            return {
                "status": "success",
                "count": len(buckets),
                "buckets": buckets,
            }
        else:
            # List objects in bucket
            bucket = client.bucket(bucket_name)
            blobs = []

            for blob in client.list_blobs(bucket, prefix=prefix):
                blobs.append(
                    {
                        "name": blob.name,
                        "size": blob.size,
                        "content_type": blob.content_type,
                        "updated": str(blob.updated),
                    }
                )

            return {
                "status": "success",
                "bucket": bucket_name,
                "count": len(blobs),
                "objects": blobs,
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bucket_name": bucket_name,
        }


async def get_object_metadata(bucket_name: str, object_name: str) -> dict:
    """
    Get metadata for a Cloud Storage object.

    Args:
        bucket_name: Bucket name
        object_name: Object path

    Returns:
        dict with object metadata
    """
    if not STORAGE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-storage not installed",
        }

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        blob.reload()

        return {
            "status": "success",
            "name": blob.name,
            "bucket": bucket_name,
            "size": blob.size,
            "content_type": blob.content_type,
            "md5_hash": blob.md5_hash,
            "created": str(blob.time_created),
            "updated": str(blob.updated),
            "public_url": blob.public_url,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bucket_name": bucket_name,
            "object_name": object_name,
        }


async def upload_file(
    bucket_name: str, source_path: str, destination_path: str
) -> dict:
    """
    Upload a file to Cloud Storage.

    Args:
        bucket_name: Bucket name
        source_path: Local file path
        destination_path: Destination path in bucket

    Returns:
        dict with upload status
    """
    if not STORAGE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-storage not installed",
        }

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_path)

        blob.upload_from_filename(source_path)

        return {
            "status": "success",
            "bucket": bucket_name,
            "destination": destination_path,
            "source": source_path,
            "size": blob.size,
            "public_url": blob.public_url,
            "message": f"File uploaded successfully to gs://{bucket_name}/{destination_path}",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bucket_name": bucket_name,
            "source_path": source_path,
        }
