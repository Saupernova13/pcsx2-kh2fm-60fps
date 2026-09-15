# v01 - widescreen 19.5:9 for the S24 Ultra

| | |
|---|---|
| Tag | none - v01 shipped into the user's PCSX2 before this repo existed; see "Get this version" |
| Date | 2026-09-14 |
| Built on | ElHecht's `[Widescreen 16:9]` from PCSX2's database patch for SLPM-66675 |
| Groups | 1 of ours: `[Widescreen 19.5:9 - S24 Ultra]`, 15 patch lines when built |
| Confidence | Arithmetic verified; **not seen on screen, not yet reported on by the user\*** |

## What it changed

The user asked, with the BT3 repo as the reference, for their 16:9 patch to be
switched off and a patch rendering at the S24 Ultra's aspect added and enabled.

In the user's PCSX2 (`EmuDeck\Emulators\PCSX2-Qt`):

- `patches\SLPM-66675_FAF99301.pnach`: added `[Widescreen 19.5:9 - S24 Ultra]`,
  leaving `[Widescreen 16:9]` in the file.
- `gamesettings\SLPM-66675_FAF99301.ini`: `Enable = Widescreen 16:9` replaced by
  `Enable = Widescreen 19.5:9 - S24 Ultra`. Remove Blackbars, Remove Blur, Swap X
  and O and 60 FPS stayed on.
- Backups of both files as `*.bak-20260914`.

The group is ElHecht's 16:9 group with five words changed and one added. This
repo keeps only those changes, in
[`patch/widescreen-19.5x9-s24.json`](../../patch/widescreen-19.5x9-s24.json):

| Address | 16:9 group | This group | |
|---|---|---|---|
| `00106E54` | `3C1B3F40` | `3C1B3F1D` | `lui $k1, 0x3F1D` - high half of 12/19.5 |
| `00106E58` | `449BF000` | `377B89D9` | `ori $k1, $k1, 0x89D9` - low half |
| `00106E60` | (stock nop) | `449BF000` | `mtc1 $k1, $f30`, moved after the `ori` |
| `2036CE94` | `3F400000` | `3F1D89D9` | font x-scale |
| `2036CE98` | `3F400000` | `3F1D89D9` | font x-scale |
| `2036CE9C` | `3F400000` | `3F1D89D9` | font x-scale |

Plus `gsaspectratio=Stretch` in place of 16:9.

## What was discovered

- **The 16:9 group is a code hack, not a data poke.** It rewrites the projection
  routine at `00106DE8` to load a 4:3 base of 0.8 and multiply it by a factor
  loaded as an instruction immediate, `lui $k1, 0x3F40` = 0.75 at `00106E54`,
  storing the product in `[cam+0x4C]`. 0.75 is `(4/3) / (16/9)`, the horizontal
  widen factor. Its three "font fix" floats at `0036CE94..9C` are the same 0.75.
- **The model reproduces the group from first principles.** Fed 16:9 it gives
  `3F400000`, bit for bit. For 19.5:9 the factor is `(4/3) / (19.5/9) = 12/19.5 =
  0.6153846 = 3F1D89D9`.
- **A bare `lui` is not enough here.** It keeps only the top 16 bits, which
  loads 0.6132812 - 0.34% narrow. The routine has two stock `nop`s right after
  the multiply's setup, so the group loads the exact word with `lui` + `ori` and
  moves the `mtc1` into the first of them. (BT3's widescreen took the
  truncation, 0.13% there, because its immediate had no room.)
- **The rest is aspect-independent** - the 0.8 base, the cutscene zoom, depth of
  field and the subtitle height - and is taken unchanged from the 16:9 group.
- **PCSX2 has no 19.5:9 display aspect**, so the group uses Stretch against a
  19.5:9 output. The user's global setting was already Stretch.
- **19.5:9 matches BT3, not the panel.** Samsung lists 3088x1440, 19.3:9. The
  group follows the BT3 patch's 3120x1440; if the device shows it slightly too
  wide, `tools/ws-math.py --aspect 3088:1440` gives the other words.
- **Never both.** Both widescreen groups write `00106E54/58` every frame, and a
  mix of the two loads a wrong float.
- **Do not touch the game's settings in PCSX2's menus while it runs** after
  editing the ini by hand: PCSX2 can save its in-memory settings over the file
  and turn 16:9 back on.

## Evidence

- `tools/ws-math.py`: `aspect 19.5:9 = 2.166667; widen factor 0.6153846 =
  3F1D89D9`, `16:9 gives 3F400000`, and the JSON agrees with the model.
- The instruction encodings decode back to the intended `lui` / `ori` / `mtc1`.
- The installed file parsed back with `Widescreen 16:9` 14 lines and
  `Widescreen 19.5:9 - S24 Ultra` 15 lines.

Not verified on screen.

## Get this version

The change set is unchanged in every later version. Build and install it:

    python tools/install.py --widescreen

That reads `[Widescreen 16:9]` from the user's own database patch, checks its 14
lines and the five words it expects, and writes the 19.5:9 group next to it.
