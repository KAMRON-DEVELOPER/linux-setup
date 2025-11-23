#!/usr/bin/env python3
"""
K3s Services Port Forward Manager
Manages all kubectl port-forward processes in one terminal.
All port forwards are automatically cleaned up when the script exits.
"""

import subprocess
import signal
import sys
import time
from typing import List

# Port forward configurations: (namespace, pod_name, local_port, remote_port)
PORT_FORWARDS = [
    ("postgres-ns", "postgres-ss-0", 5432, 5432),
    ("redis-ns", "redis-ss-0", 6379, 6379),
    ("rabbitmq-ns", "rabbitmq-ss-0", 5672, 5672),
    ("kafka-ns", "kafka-cluster-kafka-node-pool-0", 9092, 9094),
]

processes: List[subprocess.Popen] = []


def cleanup(signum=None, frame=None):
    """Cleanup all port-forward processes."""
    print("\n🧹 Cleaning up port forwards...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as e:
            print(f"Error cleaning up process: {e}")
    
    print("✓ All port forwards stopped")
    sys.exit(0)


def start_port_forward(namespace: str, pod: str, local_port: int, remote_port: int) -> subprocess.Popen:
    """Start a single kubectl port-forward process."""
    cmd = [
        "kubectl", "port-forward",
        f"pod/{pod}",
        f"{local_port}:{remote_port}",
        "-n", namespace
    ]
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    return proc


def main():
    # Register cleanup handlers
    signal.signal(signal.SIGINT, cleanup)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup)  # Kill signal
    
    print("🚀 Starting K3s Services Port Forwards")
    print("=" * 60)
    
    # Start all port forwards
    for namespace, pod, local_port, remote_port in PORT_FORWARDS:
        try:
            proc = start_port_forward(namespace, pod, local_port, remote_port)
            processes.append(proc)
            
            # Give it a moment to start
            time.sleep(0.5)
            
            # Check if process started successfully
            if proc.poll() is None:
                service_name = pod.split('-')[0]
                print(f"✓ {service_name:12} localhost:{local_port:5} → {namespace}/{pod}")
            else:
                stderr = proc.stderr.read()
                print(f"✗ Failed to forward {pod}: {stderr}")
                
        except Exception as e:
            print(f"✗ Error starting port-forward for {pod}: {e}")
    
    print("=" * 60)
    print(f"✓ {len(processes)} port forwards active")
    print("\n📝 Services available at:")
    print("   PostgreSQL:  localhost:5432")
    print("   Redis:       localhost:6379")
    print("   RabbitMQ:    localhost:5672")
    print("   Kafka:       localhost:9092")
    print("\n⚠️  Press Ctrl+C to stop all port forwards")
    print("=" * 60)
    
    # Keep the script running and monitor processes
    try:
        while True:
            time.sleep(1)
            
            # Check if any process has died
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    namespace, pod, local_port, remote_port = PORT_FORWARDS[i]
                    stderr = proc.stderr.read()
                    print(f"\n⚠️  Port forward died: {pod}")
                    if stderr:
                        print(f"   Error: {stderr}")
                    
                    # Try to restart
                    print(f"   Restarting...")
                    new_proc = start_port_forward(namespace, pod, local_port, remote_port)
                    processes[i] = new_proc
                    time.sleep(0.5)
                    if new_proc.poll() is None:
                        print(f"   ✓ Restarted successfully")
                    
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
