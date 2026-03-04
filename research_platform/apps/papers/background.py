import atexit
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

# Gracefully wait for in-flight tasks when Django/gunicorn shuts down.
# wait=True ensures background PDF processing, indexing, etc. finish before exit.
atexit.register(executor.shutdown, wait=True)