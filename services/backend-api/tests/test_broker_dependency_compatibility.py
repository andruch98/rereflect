"""Check real broker imports without opening a connection or dispatching work."""
from kombu import Connection
from kombu.transport.redis import Channel
import redis


def test_installed_redis_client_is_supported_by_broker_transport():
    # This is the runtime version gate that broke feedback creation in CI.
    channel = Channel.__new__(Channel)
    channel.global_keyprefix = ""
    assert issubclass(channel._get_client(), redis.Redis)
    with Connection("redis://localhost:6379/0") as connection:
        assert connection.transport.driver_type == "redis"
