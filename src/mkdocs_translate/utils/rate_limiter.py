import asyncio
import time
from collections import deque

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.timestamps = deque()
        self._lock = None

    def update_limit(self, rpm: int):
        self.rpm = rpm

    async def acquire(self):
        if self.rpm <= 0:
            return
        
        # Lazy initialization of the lock to ensure it belongs to the current event loop
        if self._lock is None:
            self._lock = asyncio.Lock()
        
        # Check if lock belongs to a different loop (e.g. if loop restarted)
        try:
            if self._lock._loop != asyncio.get_running_loop():
                 self._lock = asyncio.Lock()
        except AttributeError:
             # In some python versions or implementations _loop might not be directly accessible or needed checks differently
             # But generally for asyncio.Lock it is bound to a loop.
             # Safer way: just recreate if we suspect loop changed, but hard to detect without access.
             # Alternative: Processor resets the RateLimiter or we allow resetting.
             # Given the context of the error "bound to a different event loop", the above check or catching the error is needed.
             pass

        # Robust way: catch runtime error if loop mismatch occurs on acquire (though acquire is async def)
        # Actually asyncio.Lock() creates a future. 
        # Let's just recreate it if we are in a new loop? 
        # Since we can't easily detect "is this lock valid for this loop" without private API,
        # We will assume that if Processor calls us, it might be a new loop.
        # But we need to persist timestamps.
        
        # Let's try to grab the lock. If it fails due to loop mismatch, we make a new one.
        # However, 'async with' calls __aenter__. 
        
        # The safest strategy for this specific app structure (Worker creates new loop every time):
        # We should probably reset the lock at the start of the 'process_tasks' or ensure this acquire handles it.
        
        # Let's just ensure we have a lock for the CURRENT loop.
        current_loop = asyncio.get_running_loop()
        if self._lock is None or self._lock._loop != current_loop:
             self._lock = asyncio.Lock()

        async with self._lock:
            now = time.time()
            # Remove timestamps older than 60 seconds
            while self.timestamps and now - self.timestamps[0] > 60:
                self.timestamps.popleft()

            if len(self.timestamps) >= self.rpm:
                # Calculate wait time
                wait_time = 60 - (now - self.timestamps[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    while self.timestamps and now - self.timestamps[0] > 60:
                        self.timestamps.popleft()
            
            self.timestamps.append(time.time())