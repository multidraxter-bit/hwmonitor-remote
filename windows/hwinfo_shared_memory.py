"""
HWiNFO shared-memory bridge for hwremote-monitor.

This uses the publicly available reverse-engineered shared-memory layout,
adapted from the MIT-licensed `pywhinfo.py` project by warbou:
https://github.com/warbou/hwinfo-oled-monitor
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import sys
from dataclasses import dataclass


HWINFO_SHARED_MEM_PATH = "Global\\HWiNFO_SENS_SM2"
HWINFO_HEADER_MAGIC = 0x53695748
FILE_MAP_READ = 0x0004


class HWiNFOHeader(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("version", ctypes.c_uint32),
        ("revision", ctypes.c_uint32),
        ("last_update", ctypes.c_int64),
        ("sensor_section_offset", ctypes.c_uint32),
        ("sensor_element_size", ctypes.c_uint32),
        ("sensor_element_count", ctypes.c_uint32),
        ("entry_section_offset", ctypes.c_uint32),
        ("entry_element_size", ctypes.c_uint32),
        ("entry_element_count", ctypes.c_uint32),
    ]


class HWiNFOSensor(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("sensor_id", ctypes.c_uint32),
        ("sensor_instance", ctypes.c_uint32),
        ("name_original", ctypes.c_char * 128),
        ("name_user", ctypes.c_char * 128),
    ]


class HWiNFOEntry(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("sensor_type", ctypes.c_uint32),
        ("sensor_index", ctypes.c_uint32),
        ("entry_id", ctypes.c_uint32),
        ("name_original", ctypes.c_char * 128),
        ("name_user", ctypes.c_char * 128),
        ("unit", ctypes.c_char * 16),
        ("value", ctypes.c_double),
        ("value_min", ctypes.c_double),
        ("value_max", ctypes.c_double),
        ("value_avg", ctypes.c_double),
    ]


def _decode(buffer: bytes) -> str:
    return buffer.decode("utf-8", errors="ignore").rstrip("\x00").strip()


def _clean_number(value: float):
    if value != value:
        return None
    if value > sys.float_info.max or value < -sys.float_info.max:
        return None
    return round(float(value), 4)


@dataclass
class SharedMapping:
    handle: int | None = None
    ptr: int | None = None

    def close(self) -> None:
        kernel32 = ctypes.windll.kernel32
        if self.ptr:
            kernel32.UnmapViewOfFile(ctypes.c_void_p(self.ptr))
            self.ptr = None
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def read_hwinfo() -> dict:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenFileMappingW.argtypes = [
        ctypes.wintypes.DWORD,
        ctypes.wintypes.BOOL,
        ctypes.wintypes.LPCWSTR,
    ]
    kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
    kernel32.MapViewOfFile.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.c_size_t,
    ]
    kernel32.MapViewOfFile.restype = ctypes.c_void_p

    mapping = SharedMapping()
    try:
        mapping.handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, HWINFO_SHARED_MEM_PATH)
        if not mapping.handle:
            raise RuntimeError("HWiNFO shared memory is not available")

        mapping.ptr = kernel32.MapViewOfFile(mapping.handle, FILE_MAP_READ, 0, 0, 0)
        if not mapping.ptr:
            raise RuntimeError("Unable to map HWiNFO shared memory")

        header = HWiNFOHeader.from_address(mapping.ptr)
        if header.magic != HWINFO_HEADER_MAGIC:
            raise RuntimeError(f"Unexpected HWiNFO header magic 0x{header.magic:08X}")

        sensors_by_index: dict[int, str] = {}
        sensor_base = mapping.ptr + header.sensor_section_offset
        for index in range(header.sensor_element_count):
            addr = sensor_base + (index * header.sensor_element_size)
            sensor = HWiNFOSensor.from_address(addr)
            label = _decode(sensor.name_user) or _decode(sensor.name_original) or f"Sensor {index}"
            sensors_by_index[index] = label

        entries = []
        entry_base = mapping.ptr + header.entry_section_offset
        for index in range(header.entry_element_count):
            addr = entry_base + (index * header.entry_element_size)
            entry = HWiNFOEntry.from_address(addr)
            if entry.sensor_type == 0:
                continue

            entries.append(
                {
                    "group": sensors_by_index.get(entry.sensor_index, f"Sensor {entry.sensor_index}"),
                    "name": _decode(entry.name_user) or _decode(entry.name_original) or f"Entry {entry.entry_id}",
                    "sensorTypeId": int(entry.sensor_type),
                    "sensorIndex": int(entry.sensor_index),
                    "id": int(entry.entry_id),
                    "unit": _decode(entry.unit),
                    "value": _clean_number(entry.value),
                    "min": _clean_number(entry.value_min),
                    "max": _clean_number(entry.value_max),
                    "avg": _clean_number(entry.value_avg),
                }
            )

        return {
            "source": "HWiNFO",
            "mode": "shared_memory",
            "version": f"{header.version}.{header.revision}",
            "sensorCount": len(entries),
            "sensors": entries,
        }
    finally:
        mapping.close()


def main() -> int:
    try:
        payload = read_hwinfo()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
