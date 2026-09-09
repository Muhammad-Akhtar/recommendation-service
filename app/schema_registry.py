"""Schema Registry client (Apicurio ccompat) + Avro wire-format encode/decode.

Uses Apicurio's Confluent-compatible API (`/apis/ccompat/v7`) so the same
subject/register/id endpoints work with Confluent Avro wire format:

  magic byte (0) + schema id (4 bytes, big-endian) + Avro payload
"""

from __future__ import annotations

import json
import struct
from io import BytesIO
from pathlib import Path

import fastavro
import httpx

AVRO_DIR = Path(__file__).resolve().parent / "avro"
MAGIC_BYTE = 0
# Confluent / Apicurio ccompat content type
_SR_CONTENT_TYPE = "application/vnd.schemaregistry.v1+json"


def load_avro_schema(filename: str = "user_interaction.avsc") -> dict:
    path = AVRO_DIR / filename
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class SchemaRegistryClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        # Expect Apicurio ccompat base, e.g. http://schema-registry:8080/apis/ccompat/v7
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._schema_by_id: dict[int, dict] = {}

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": _SR_CONTENT_TYPE, "Accept": _SR_CONTENT_TYPE},
        )

    def ping(self) -> bool:
        try:
            with self._client() as client:
                response = client.get("/subjects")
                return response.status_code == 200
        except Exception:
            return False

    def set_compatibility(self, subject: str, level: str = "FULL") -> None:
        with self._client() as client:
            response = client.put(
                f"/config/{subject}",
                json={"compatibility": level},
            )
            # 404 before first schema is ok — register first, then set.
            if response.status_code not in (200, 404):
                response.raise_for_status()

    def register_schema(self, subject: str, schema: dict) -> int:
        payload = {"schema": json.dumps(schema)}
        with self._client() as client:
            response = client.post(
                f"/subjects/{subject}/versions",
                json=payload,
            )
            response.raise_for_status()
            schema_id = int(response.json()["id"])
        self._schema_by_id[schema_id] = schema
        return schema_id

    def get_schema_by_id(self, schema_id: int) -> dict:
        if schema_id in self._schema_by_id:
            return self._schema_by_id[schema_id]
        with self._client() as client:
            response = client.get(f"/schemas/ids/{schema_id}")
            response.raise_for_status()
            schema = json.loads(response.json()["schema"])
        self._schema_by_id[schema_id] = schema
        return schema


def encode_avro_message(schema_id: int, schema: dict, record: dict) -> bytes:
    buffer = BytesIO()
    buffer.write(struct.pack(">bI", MAGIC_BYTE, schema_id))
    fastavro.schemaless_writer(buffer, fastavro.parse_schema(schema), record)
    return buffer.getvalue()


def decode_avro_message(
    payload: bytes,
    registry: SchemaRegistryClient,
    reader_schema: dict | None = None,
) -> dict:
    if not payload or payload[0:1] != bytes([MAGIC_BYTE]):
        raise ValueError("Not an Avro Confluent-wire payload (missing magic byte)")

    schema_id = struct.unpack(">I", payload[1:5])[0]
    writer_schema = registry.get_schema_by_id(schema_id)
    writer_parsed = fastavro.parse_schema(writer_schema)
    reader_parsed = (
        fastavro.parse_schema(reader_schema) if reader_schema else writer_parsed
    )
    return fastavro.schemaless_reader(
        BytesIO(payload[5:]),
        writer_parsed,
        reader_parsed,
    )


def event_to_avro_record(event) -> dict:
    """Convert Pydantic UserInteractionEvent to an Avro-friendly dict."""
    data = event.model_dump()
    # Avro union ["null","string"] expects None, not omitted inconsistently.
    if data.get("device_type") is None:
        data["device_type"] = None
    return data
