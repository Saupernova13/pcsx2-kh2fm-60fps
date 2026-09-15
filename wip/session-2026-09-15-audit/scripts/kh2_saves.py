import struct, pathlib
for n in ("00", "01", "02"):
    icon = pathlib.Path(f"work/saves/FM-{n}.icon.sys").read_bytes()
    title = icon[0xC0:0xC0 + 68].split(b"\0\0", 1)[0]
    try:
        t = title.decode("shift_jis", "replace")
    except Exception:
        t = repr(title)
    data = pathlib.Path(f"work/saves/FM-{n}.bin").read_bytes()
    print(f"== FM-{n}: icon title {t!r}  size {len(data)}")
    for off in range(0, 0x40, 16):
        print(f"   {off:04X}  " + " ".join(f"{b:02X}" for b in data[off:off + 16]))
