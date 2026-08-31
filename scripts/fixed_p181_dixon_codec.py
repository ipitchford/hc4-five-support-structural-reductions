#!/usr/bin/env python3
"""Canonical HC4DXN01 binary container codec.

The module is intentionally algebra-agnostic.  It implements only Amendment
01 Section 3 and exposes exact payload constructors plus a strict reader.
"""

from __future__ import annotations

import array
import hashlib
import math
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Sequence


MAGIC = b"HC4DXN01"
SCHEMA_MAJOR = 1
BYTE_ORDER_CODE = 1
HEADER = struct.Struct("<8sHBBIQQ")
DTYPE_CODES = {"u8": 1, "u32": 2, "u64": 3, "bigint": 4, "bytes": 5}
CODE_DTYPES = {value: key for key, value in DTYPE_CODES.items()}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encode_bigint(value: int) -> bytes:
    value = int(value)
    if value == 0:
        return b"\x00" + struct.pack("<I", 0)
    sign = 1 if value > 0 else 2
    magnitude = abs(value)
    length = (magnitude.bit_length() + 7) // 8
    raw = magnitude.to_bytes(length, "little")
    if not raw or raw[-1] == 0:
        raise AssertionError("nonminimal bigint encoder")
    return bytes([sign]) + struct.pack("<I", length) + raw


def decode_bigint(payload: bytes, offset: int = 0) -> tuple[int, int]:
    if offset + 5 > len(payload):
        raise ValueError("truncated bigint header")
    sign = payload[offset]
    length = struct.unpack_from("<I", payload, offset + 1)[0]
    end = offset + 5 + length
    if end > len(payload):
        raise ValueError("truncated bigint magnitude")
    raw = payload[offset + 5 : end]
    if sign == 0:
        if length != 0:
            raise ValueError("zero bigint has a magnitude")
        return 0, end
    if sign not in (1, 2) or length == 0 or raw[-1] == 0:
        raise ValueError("noncanonical bigint")
    magnitude = int.from_bytes(raw, "little")
    return (magnitude if sign == 1 else -magnitude), end


def payload_u8(values: Iterable[int]) -> bytes:
    result = bytes(int(value) for value in values)
    return result


def payload_u32(values: Iterable[int]) -> bytes:
    packed = array.array("I", (int(value) for value in values))
    if sys.byteorder != "little":
        packed.byteswap()
    return packed.tobytes()


def payload_u64(values: Iterable[int]) -> bytes:
    packed = array.array("Q", (int(value) for value in values))
    if sys.byteorder != "little":
        packed.byteswap()
    return packed.tobytes()


def payload_bigints(values: Iterable[int]) -> bytes:
    payload = bytearray()
    for value in values:
        payload.extend(encode_bigint(value))
    return bytes(payload)


def shape_product(shape: Sequence[int]) -> int:
    return math.prod(map(int, shape)) if shape else 1


@dataclass(frozen=True)
class ArrayPayload:
    dtype: str
    shape: tuple[int, ...]
    payload: bytes

    def validate(self) -> None:
        if self.dtype not in DTYPE_CODES:
            raise ValueError(f"unknown dtype {self.dtype}")
        if any(int(value) < 0 for value in self.shape):
            raise ValueError("negative array shape")
        count = shape_product(self.shape)
        if self.dtype == "u8" and len(self.payload) != count:
            raise ValueError("u8 payload length mismatch")
        if self.dtype == "u32" and len(self.payload) != 4 * count:
            raise ValueError("u32 payload length mismatch")
        if self.dtype == "u64" and len(self.payload) != 8 * count:
            raise ValueError("u64 payload length mismatch")
        if self.dtype == "bytes" and (
            len(self.shape) != 1 or self.shape[0] != len(self.payload)
        ):
            raise ValueError("raw-byte array must have its byte length as shape")
        if self.dtype == "bigint":
            offset = 0
            for _ in range(count):
                _value, offset = decode_bigint(self.payload, offset)
            if offset != len(self.payload):
                raise ValueError("extra bytes after bigint vector")


@dataclass(frozen=True)
class ArrayDescriptor:
    name: str
    dtype: str
    shape: tuple[int, ...]
    offset: int
    byte_length: int
    sha256: str


def _validate_name(name: str) -> bytes:
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("array name is not ASCII") from exc
    if not encoded or len(encoded) > 65535 or any(byte < 32 or byte > 126 for byte in encoded):
        raise ValueError("array name is not nonempty printable ASCII")
    return encoded


def _descriptor_size(name: str, rank: int) -> int:
    return 2 + len(_validate_name(name)) + 1 + 1 + 2 + 8 * rank + 8 + 8 + 32


def write_container(path: Path, arrays: dict[str, ArrayPayload]) -> dict[str, object]:
    """Write one complete container to a path that must not already exist."""

    if not arrays:
        raise ValueError("container has no arrays")
    names = sorted(arrays, key=lambda item: item.encode("ascii"))
    if len(set(names)) != len(names):
        raise ValueError("duplicate array names")
    for name in names:
        _validate_name(name)
        arrays[name].validate()

    table_bytes = sum(_descriptor_size(name, len(arrays[name].shape)) for name in names)
    payload_offset = HEADER.size + table_bytes
    descriptors: list[ArrayDescriptor] = []
    cursor = payload_offset
    for name in names:
        item = arrays[name]
        descriptors.append(
            ArrayDescriptor(
                name=name,
                dtype=item.dtype,
                shape=item.shape,
                offset=cursor,
                byte_length=len(item.payload),
                sha256=sha256_bytes(item.payload),
            )
        )
        cursor += len(item.payload)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(
            HEADER.pack(
                MAGIC,
                SCHEMA_MAJOR,
                BYTE_ORDER_CODE,
                0,
                len(descriptors),
                table_bytes,
                payload_offset,
            )
        )
        for descriptor in descriptors:
            name_bytes = descriptor.name.encode("ascii")
            handle.write(struct.pack("<H", len(name_bytes)))
            handle.write(name_bytes)
            handle.write(
                struct.pack(
                    "<BBH",
                    DTYPE_CODES[descriptor.dtype],
                    len(descriptor.shape),
                    0,
                )
            )
            for dimension in descriptor.shape:
                handle.write(struct.pack("<Q", int(dimension)))
            handle.write(struct.pack("<QQ", descriptor.offset, descriptor.byte_length))
            handle.write(bytes.fromhex(descriptor.sha256))
        if handle.tell() != payload_offset:
            raise AssertionError("descriptor table length drift")
        for descriptor in descriptors:
            handle.write(arrays[descriptor.name].payload)
        if handle.tell() != cursor:
            raise AssertionError("container length drift")
        handle.flush()
        os.fsync(handle.fileno())

    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "byte_count": path.stat().st_size,
        "arrays": {
            item.name: {
                "dtype": item.dtype,
                "shape": list(item.shape),
                "offset": item.offset,
                "byte_length": item.byte_length,
                "sha256": item.sha256,
            }
            for item in descriptors
        },
    }


def _read_exact(handle: BinaryIO, count: int) -> bytes:
    payload = handle.read(count)
    if len(payload) != count:
        raise ValueError("truncated container")
    return payload


def read_descriptors(path: Path) -> dict[str, ArrayDescriptor]:
    file_size = path.stat().st_size
    with path.open("rb") as handle:
        header = HEADER.unpack(_read_exact(handle, HEADER.size))
        magic, major, endian, reserved, array_count, table_bytes, payload_offset = header
        if (
            magic != MAGIC
            or major != SCHEMA_MAJOR
            or endian != BYTE_ORDER_CODE
            or reserved != 0
            or payload_offset != HEADER.size + table_bytes
        ):
            raise ValueError("invalid container header")
        descriptors: dict[str, ArrayDescriptor] = {}
        ordered_names: list[str] = []
        table_start = handle.tell()
        for _ in range(array_count):
            name_length = struct.unpack("<H", _read_exact(handle, 2))[0]
            name = _read_exact(handle, name_length).decode("ascii")
            _validate_name(name)
            dtype_code, rank, flags = struct.unpack("<BBH", _read_exact(handle, 4))
            if dtype_code not in CODE_DTYPES or flags != 0:
                raise ValueError("invalid descriptor type or flags")
            shape = tuple(
                struct.unpack("<Q", _read_exact(handle, 8))[0] for _ in range(rank)
            )
            offset, length = struct.unpack("<QQ", _read_exact(handle, 16))
            digest_hex = _read_exact(handle, 32).hex()
            if name in descriptors:
                raise ValueError("duplicate descriptor")
            descriptor = ArrayDescriptor(
                name, CODE_DTYPES[dtype_code], shape, offset, length, digest_hex
            )
            descriptors[name] = descriptor
            ordered_names.append(name)
        if handle.tell() - table_start != table_bytes or handle.tell() != payload_offset:
            raise ValueError("descriptor table size mismatch")
        if ordered_names != sorted(ordered_names, key=lambda item: item.encode("ascii")):
            raise ValueError("descriptor order is not canonical")
        cursor = payload_offset
        for name in ordered_names:
            descriptor = descriptors[name]
            if descriptor.offset != cursor:
                raise ValueError("nonminimal payload offset")
            cursor += descriptor.byte_length
        if cursor != file_size:
            raise ValueError("container has missing or extra bytes")
    return descriptors


def read_array(path: Path, descriptor: ArrayDescriptor) -> bytes:
    with path.open("rb") as handle:
        handle.seek(descriptor.offset)
        payload = _read_exact(handle, descriptor.byte_length)
    if sha256_bytes(payload) != descriptor.sha256:
        raise ValueError(f"payload hash mismatch: {descriptor.name}")
    ArrayPayload(descriptor.dtype, descriptor.shape, payload).validate()
    return payload


def decode_u32(payload: bytes) -> list[int]:
    if len(payload) % 4:
        raise ValueError("u32 payload has fractional element")
    return [item[0] for item in struct.iter_unpack("<I", payload)]


def decode_u64(payload: bytes) -> list[int]:
    if len(payload) % 8:
        raise ValueError("u64 payload has fractional element")
    return [item[0] for item in struct.iter_unpack("<Q", payload)]


def decode_bigints(payload: bytes, count: int) -> list[int]:
    values = []
    offset = 0
    for _ in range(count):
        value, offset = decode_bigint(payload, offset)
        values.append(value)
    if offset != len(payload):
        raise ValueError("extra bytes after bigint array")
    return values
