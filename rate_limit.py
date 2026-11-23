
import math
import time

from redis_client import redis_client


CAPACITY = 5
REFILL_RATE = 0.5  # Tokens per second
BUCKET_TTL = 20    # Seconds


TOKEN_BUCKET_SCRIPT = """
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local values = redis.call(
    "HMGET", KEYS[1], "tokens", "updated_at"
)

local tokens = tonumber(values[1])
local last_updated = tonumber(values[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
end

local elapsed = math.max(0, now - last_updated)

tokens = math.min(
    capacity,
    tokens + elapsed * refill_rate
)

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after = (1 - tokens) / refill_rate
end

redis.call(
    "HSET", KEYS[1],
    "tokens", tokens,
    "updated_at", now
)

redis.call("EXPIRE", KEYS[1], ttl)

return {allowed, retry_after, tokens}
"""


def check_rate_limit(client_id: str) -> tuple[bool, int]:
    key = f"rate_limit:reports:{client_id}"

    result = redis_client.eval(
        TOKEN_BUCKET_SCRIPT,
        1,
        key,
        CAPACITY,
        REFILL_RATE,
        time.time(),
        BUCKET_TTL,
    )

    allowed = bool(int(result[0]))
    retry_after = math.ceil(float(result[1]))

    return allowed, retry_after