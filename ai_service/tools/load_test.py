import asyncio
import time
import urllib.request
import urllib.parse
import json
import sys

# Target configuration
BASE_URL = "http://localhost:8000"
SERVICE_KEY = "test-key-123"  # Standard dev service key

async def test_endpoint(session, name, path, method="GET", payload=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "x-service-key": SERVICE_KEY,
        "Content-Type": "application/json"
    }
    
    data = None
    if payload:
        data = json.dumps(payload).encode("utf-8")
        
    start_time = time.perf_counter()
    try:
        # Define the network request inside a thread pool to avoid blocking asyncio
        def perform_request():
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read(), response.status
                
        loop = asyncio.get_running_loop()
        body, status = await loop.run_in_executor(None, perform_request)
        latency = (time.perf_counter() - start_time) * 1000
        return True, latency, status
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return False, latency, str(e)

async def run_benchmark(concurrency, total_requests):
    print("=" * 60)
    print(f"Starting Load Test: Concurrency={concurrency}, Total Requests={total_requests}")
    print(f"Targeting: {BASE_URL}")
    print("=" * 60)
    
    # We will query '/health' and '/cases' as a baseline load
    sem = asyncio.Semaphore(concurrency)
    
    async def worker():
        async with sem:
            # We run health check first, then list cases
            success, latency, res = await test_endpoint(None, "health", "/health", "GET")
            return success, latency, res

    tasks = [worker() for _ in range(total_requests)]
    
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time
    
    successes = [r for r in results if r[0]]
    failures = [r for r in results if not r[0]]
    latencies = [r[1] for r in results]
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    min_latency = min(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    throughput = len(results) / total_time if total_time > 0 else 0
    
    print("\nBenchmark Results Summary:")
    print("-" * 40)
    print(f"Total Completed Requests: {len(results)}")
    print(f"Successful Requests:      {len(successes)} ({len(successes)/len(results)*100:.1f}%)")
    print(f"Failed Requests:          {len(failures)} ({len(failures)/len(results)*100:.1f}%)")
    print(f"Total Test Time:          {total_time:.2f} seconds")
    print(f"Throughput (RPS):         {throughput:.2f} req/sec")
    print("-" * 40)
    print("Latency Statistics:")
    print(f"  Average Latency:        {avg_latency:.2f} ms")
    print(f"  Min Latency:            {min_latency:.2f} ms")
    print(f"  Max Latency:            {max_latency:.2f} ms")
    print("=" * 60)

if __name__ == "__main__":
    concurrency = 5
    total = 25
    
    if len(sys.argv) > 1:
        try:
            concurrency = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            total = int(sys.argv[2])
        except ValueError:
            pass
            
    asyncio.run(run_benchmark(concurrency, total))
