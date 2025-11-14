"""Cache .lit_test_times.txt files between premerge invocations.

.lit_test_times.txt files are used by lit to order tests to maximize parallelism.
Caching them can improve test times by ~15%. This script handles downloading
cached files and uploading new versions to GCS buckets.
"""

import glob
import logging
import multiprocessing.pool
import os
import pathlib
import sys

from google.cloud import storage
from google.api_core import exceptions

GCS_PARALLELISM = 100


def _upload_timing_file(bucket, timing_file_path):
    """Upload a single timing file to GCS if it exists."""
    if os.path.exists(timing_file_path):
        blob = bucket.blob("lit_timing/" + timing_file_path)
        blob.upload_from_filename(timing_file_path)


def upload_timing_files(storage_client, bucket_name: str):
    """Upload all timing files to GCS bucket."""
    bucket = storage_client.bucket(bucket_name)
    
    with multiprocessing.pool.ThreadPool(GCS_PARALLELISM) as pool:
        timing_files = glob.glob("**/.lit_test_times.txt", recursive=True)
        pool.starmap(_upload_timing_file, [(bucket, path) for path in timing_files])
    
    logging.info("Done uploading timing files")


def _download_timing_file(blob):
    """Download a single timing file from GCS."""
    file_name = blob.name.removeprefix("lit_timing/")
    pathlib.Path(os.path.dirname(file_name)).mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(file_name)


def download_timing_files(storage_client, bucket_name: str):
    """Download all timing files from GCS bucket."""
    bucket = storage_client.bucket(bucket_name)
    
    try:
        blobs = list(bucket.list_blobs(prefix="lit_timing"))
    except exceptions.ClientError as error:
        logging.warning("Failed to list blobs in bucket: %s", error)
        return

    with multiprocessing.pool.ThreadPool(GCS_PARALLELISM) as pool:
        pool.map(_download_timing_file, blobs)
    
    logging.info("Done downloading timing files")


def main():
    if len(sys.argv) != 2:
        logging.error("Usage: %s <upload|download>", sys.argv[0])
        sys.exit(1)

    action = sys.argv[1]
    storage_client = storage.Client()
    bucket_name = os.environ["CACHE_GCS_BUCKET"]

    if action == "download":
        download_timing_files(storage_client, bucket_name)
    elif action == "upload":
        upload_timing_files(storage_client, bucket_name)
    else:
        logging.error("Invalid action. Use 'upload' or 'download'")
        sys.exit(1)


if __name__ == "__main__":
    main()
