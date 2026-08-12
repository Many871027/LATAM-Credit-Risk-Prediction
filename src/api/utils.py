import time
from collections import deque
import logging
import threading

logger = logging.getLogger("LatencyTracker")

class LatencyTracker:
    """
    Tracks endpoint latency and calculates a rolling average over a window of time.
    """
    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self.history = deque()
        self._lock = threading.Lock()

    def record_latency(self, latency_ms: float) -> float:
        """
        Records a new latency measurement, prunes old data, and returns the average latency.
        Logs a high-priority warning if the rolling average exceeds 100ms.
        """
        with self._lock:
            now = time.time()
            self.history.append((now, latency_ms))
            
            # Prune records older than window
            cutoff = now - self.window_seconds
            while self.history and self.history[0][0] < cutoff:
                self.history.popleft()
                
            # Calculate average
            total_latency = sum(item[1] for item in self.history)
            avg_latency = total_latency / len(self.history) if self.history else 0.0
            
        if avg_latency > 100.0:
            logger.warning(
                f"[HIGH-PRIORITY WARNING] Average endpoint latency exceeds 100ms SLA over rolling 1-minute window: "
                f"{avg_latency:.2f}ms (window size: {len(self.history)} requests)"
            )
            
        return avg_latency
