# Apex Noir 07 — TORCS custom livery

Original custom artwork for the `car1-ow1` car driven by `scr_server 1`. Deep graphite/navy paint, aqua aero ribbons, restrained gold pinlines, smoked silver cockpit details, and racing number `07` create a clean motorsport identity. No sponsor or third-party logo is used.

## Files

- `car1-ow1.rgb` — 512 × 512 SGI RGB/RGBA texture used by TORCS.
- `apex-noir-07.png` — viewable texture atlas and editable raster source.
- `render_livery.py` — original procedural artwork source; requires Pillow and the Windows Bahnschrift font only if you want to regenerate the assets. The race controller has no dependency on either.
- `left-side.png`, `right-side.png`, `rear-view.png` — genuine TORCS screenshots captured after installing the texture. Only the Windows title bar was cropped to remove a local personal file path.

## Install

The tested driver is `scr_server 1`, whose TORCS robot index is `0`. With TORCS closed, back up the existing texture and copy `car1-ow1.rgb` to:

`<TORCS_HOME>/drivers/scr_server/0/car1-ow1.rgb`

Start TORCS and select Quick Race → Corkscrew → `scr_server 1`. Other drivers may use another numbered folder. The car model calls this SGI texture by the exact filename `car1-ow1.rgb`.

## Restore

Stop TORCS and put your backed-up `drivers/scr_server/0/car1-ow1.rgb` back in that location. The original car-wide texture under `cars/car1-ow1/` is untouched by this package.

## Scope and visual check

The installed livery changes appearance only. It does not change car XML, physics, controller code, the track, or the retained 67.064-second result. The TORCS screenshots show the aqua/navy pattern on both sides and the rear. This older model maps a small race number clearly on one cockpit side; the corresponding number on the opposite side is less prominent. No mirrored text was observed.
