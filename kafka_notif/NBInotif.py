# kafka_notif/NBInotif.py
import logging
import threading
import time
from typing import Optional, Dict
from queue import Queue

from kafka import KafkaConsumer

logger = logging.getLogger(__name__)

# Shared queue for incoming Kafka messages (other modules import this)
message_queue: Queue = Queue()


class KafkaNotifier:
    """
    Background Kafka consumer that pushes decoded messages onto a queue.
    """

    def __init__(
        self,
        broker: str,
        topic: str,
        group_id: str,
        message_queue: Queue,
        auto_offset_reset: str = "latest",
        poll_interval: float = 1.0,
    ):
        self.broker = broker
        self.topic = topic
        self.group_id = group_id
        self.queue = message_queue
        self.auto_offset_reset = auto_offset_reset
        self.poll_interval = poll_interval

        self._consumer: Optional[KafkaConsumer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the Kafka consumer in a background thread."""
        if self._running:
            logger.warning("KafkaNotifier already running")
            return
        self._running = True
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        logger.info(
            "KafkaNotifier started (broker=%s, topic=%s, group_id=%s)",
            self.broker,
            self.topic,
            self.group_id,
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the consumer loop to stop and wait for the thread to join."""
        self._running = False
        if self._thread:
            self._thread.join(timeout)
            logger.info("KafkaNotifier stopped")

    def _consume_loop(self) -> None:
        """Internal loop: poll Kafka and push messages to the queue."""
        try:
            self._consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.broker,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
            )
            # Iterate over messages; KafkaConsumer is iterable.
            for msg in self._consumer:
                if not self._running:
                    break
                try:
                    decoded = msg.value.decode("utf-8")
                except Exception:
                    # Fallback to raw bytes if decode fails
                    decoded = str(msg.value)
                logger.info("Kafka message received: %s", decoded)
                self.queue.put(decoded)
                # Gentle pacing so logs/queue consumers aren’t overwhelmed
                time.sleep(self.poll_interval)
        except Exception as e:
            logger.error("KafkaNotifier error: %s", e)
        finally:
            try:
                if self._consumer:
                    self._consumer.close()
            except Exception:
                pass


# Optional module-level singleton holder so app code can remain simple.
_notifier: Optional[KafkaNotifier] = None


def create_notifier_from_config(cfg: Dict) -> KafkaNotifier:
    """
    Factory to build a KafkaNotifier from the dict returned by load_kafka_config().
    """
    return KafkaNotifier(
        broker=cfg["broker"],
        topic=cfg["topic"],
        group_id=cfg["group_id"],
        message_queue=message_queue,
        auto_offset_reset=cfg.get("auto_offset_reset", "latest"),
        poll_interval=float(cfg.get("poll_interval", 1.0)),
    )


def start_kafka_consumer(cfg: Dict) -> None:
    """
    Start the Kafka consumer based on config.
    Safe to call more than once; it won’t start duplicate threads.
    """
    global _notifier
    if not cfg.get("enabled", True):
        logger.info("KafkaNotifier disabled by config; not starting.")
        return
    if _notifier is None:
        _notifier = create_notifier_from_config(cfg)
    _notifier.start()


def stop_kafka_consumer(timeout: float = 5.0) -> None:
    """
    Stop the background consumer (if running).
    """
    global _notifier
    if _notifier is not None:
        _notifier.stop(timeout)
