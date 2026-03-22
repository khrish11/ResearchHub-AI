import { useEffect, useState, useRef } from 'react';

type RealtimeConfig = {
  url: string;
  onData: (data: any) => void;
  pollingIntervalMs?: number;
  onPollingTick?: () => void;
};

export function useRealtimeData({
  url,
  onData,
  pollingIntervalMs = 30000,
  onPollingTick
}: RealtimeConfig) {
  const [isStreaming, setIsStreaming] = useState(false);
  const streamAttemptFailed = useRef(false);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let pollInterval: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (pollInterval) return;
      pollInterval = setInterval(() => {
        if (document.visibilityState === 'visible') {
          onPollingTick?.();
        }
      }, pollingIntervalMs);
    };

    const stopPolling = () => {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    };

    if (!streamAttemptFailed.current) {
      // Try to connect to Server-Sent Events stream
      try {
        eventSource = new EventSource(url);
        
        eventSource.onopen = () => {
          setIsStreaming(true);
          stopPolling(); // Disable polling if stream is fully connected
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            onData(data);
          } catch (e) {
            console.error('Failed to parse realtime stream payload', e);
          }
        };

        eventSource.onerror = (err) => {
          // If connection fails, fallback to polling
          console.warn('Real-time stream connection failed or dropped, falling back to polling.', err);
          streamAttemptFailed.current = true;
          eventSource?.close();
          setIsStreaming(false);
          startPolling();
        };
      } catch (err) {
        streamAttemptFailed.current = true;
        startPolling();
      }
    } else {
      // Stream previously failed, use polling immediately
      startPolling();
    }

    // Cleanup on unmount or url change
    return () => {
      if (eventSource) eventSource.close();
      stopPolling();
    };
  }, [url, onData, pollingIntervalMs, onPollingTick]);

  return { isStreaming };
}
