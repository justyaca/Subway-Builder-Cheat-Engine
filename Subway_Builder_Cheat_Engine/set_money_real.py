import json, struct, gzip
from pathlib import Path
from io import BytesIO
import zlib

MAGIC = b"METR"
GZIP_OFFSET = 24
SIZE_OFFSET = 28
CRC_OFFSET  = 912

INFILE  = Path("save.metro")
OUTFILE = Path("save_modified.metro")
BACKUP  = Path("save_backup.metro")

def read_u32_le(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]

def write_u32_le(barr: bytearray, off: int, value: int) -> None:
    struct.pack_into("<I", barr, off, value & 0xFFFFFFFF)

def gzip_compress(data: bytes, level: int = 9) -> bytes:
    out = BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=level, mtime=0) as gz:
        gz.write(data)
    return out.getvalue()

def main():
    if not INFILE.is_file():
        print("ERROR: save.metro not found in this folder.")
        print("Put your save file here and name it exactly: save.metro")
        input("\nPress Enter to exit...")
        return

    raw = INFILE.read_bytes()
    if raw[:4] != MAGIC:
        print("ERROR: Not a .metro file (missing METR header).")
        input("\nPress Enter to exit...")
        return

    # Backup original once (won't overwrite existing backup)
    if not BACKUP.exists():
        BACKUP.write_bytes(raw)
        print(f"Backup created: {BACKUP.name}")
    else:
        print(f"Backup already exists: {BACKUP.name} (leaving as-is)")

    gzip_start = read_u32_le(raw, GZIP_OFFSET)
    header = bytearray(raw[:gzip_start])
    gzip_blob = raw[gzip_start:]

    obj = json.loads(gzip.decompress(gzip_blob).decode("utf-8"))

    ms = obj["mainSave"]
    meta = ms["metadata"]
    data = ms["data"]

    balances = None
    last_balance = None
    try:
        balances = data["financialHistory"]["entries"]
        if balances:
            last_balance = balances[-1].get("balance", None)
    except Exception:
        balances = None

    print("\nDetected values:")
    print("  metadata.money:", meta.get("money"))
    print("  data.money:    ", data.get("money"))
    print("  last balance:  ", last_balance)

    while True:
        s = input("\nEnter NEW money value (number): ").strip()
        try:
            new_money = float(s)
            break
        except ValueError:
            print("Please enter a valid number, e.g. 12345 or 12345.67")

    # Update fields
    meta["money"] = new_money
    data["money"] = new_money

    if balances and isinstance(balances, list) and len(balances) > 0:
        balances[-1]["balance"] = new_money
        print("Updated last balance entry.")
    else:
        print("WARNING: No financialHistory.entries found; only updated mainSave.*.money")

    # Re-encode + recompress
    new_json = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    new_gzip = gzip_compress(new_json, level=9)

    # Update header fields
    write_u32_le(header, SIZE_OFFSET, len(new_gzip))
    write_u32_le(header, CRC_OFFSET, zlib.crc32(new_gzip) & 0xFFFFFFFF)

    OUTFILE.write_bytes(bytes(header) + new_gzip)

    print("\nSUCCESS.")
    print(f"Wrote: {OUTFILE.name}")
    print("Reminder: fully restart the game after replacing the save (cache).")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
