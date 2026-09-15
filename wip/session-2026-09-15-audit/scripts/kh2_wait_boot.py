import sys, time
sys.path.insert(0, r"%USERPROFILE%\Documents\GitHub\pcsxroo\pcsxroo")
from ps2ee.roo import Roo
r = Roo().connect()
t0 = time.time()
while time.time() - t0 < 110:
    st = r.status()
    state = st.get("vm_state") or st.get("state")
    if state in ("running", "paused"):
        break
    time.sleep(2)
print({k: st.get(k) for k in ("vm_state", "state", "game", "serial", "crc", "title") if k in st} or st)
