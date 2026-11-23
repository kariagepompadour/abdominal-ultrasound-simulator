# Abdominal Ultrasound Simulator

[日本語](README_JA.md) · [Open the web app](https://abdominal-ultrasound-simulator.onrender.com/web)

An educational prototype that renders schematic ultrasound views from a simplified 3D abdominal model at five probe positions. It does not contain patient images, establish normal ultrasound appearances, or provide diagnostic guidance. Organ shapes, scan orientation, liver segment boundaries, and correspondence with reference views have not been validated by a specialist.

## Use

1. Open the [web app](https://abdominal-ultrasound-simulator.onrender.com/web) on a PC and choose the epigastric, right subcostal, right flank, left flank, or lower abdominal region. Rendering runs in each PC's browser.
2. The PC alone supports these controls (no phone needed):
   - **Change region**: `←` / `→` or `Space`
   - **Fine position**: `Shift` plus an arrow key (0.5 cm per press, within ±1.5 cm of the selected region), or drag the body marker
   - **Rotate**: `Q` rotates the probe counterclockwise and `E` clockwise, as seen on the body marker (5° per press, repeats while held, up to ±90°). The Yaw slider changes the same angle.
   - **Tilt**: **on the echo image** on the right, hold `Option` on Mac or `Alt` on Windows and drag with the mouse. Up tilts the modeled beam toward the head, down toward the feet, left toward the patient's right, and right toward the patient's left. Release the mouse to keep the angle. Once a drag starts, it continues until the mouse is released, even if the key is released first. With the same key held, two-finger trackpad scrolling or the mouse wheel also tilts the beam, in the same direction as dragging the image the way the scroll would move it; add `Shift` to tilt left or right with a mouse wheel. While the key is held, the hint at the lower left of the echo image switches to a direction guide. The Pitch and Roll sliders change the same angles.
   - **Other**: `F` toggles FREEZE, `R` returns to the reference view, and holding `P` applies modeled compression.
3. For optional phone control, open “Mobile Probe (QR)”. Compare the confirmation code on the phone and PC, then approve on the PC. A QR code alone cannot take control. PC tilt stays in effect until a new phone exploration starts.

Phone control needs HTTPS and a browser with orientation sensor support. Render's free instance can take longer to respond after inactivity. Reloading the page or restarting the server requires a new QR code. The server holds pairing sessions in memory; image and 3D rendering run locally in each PC browser.

## Public deployment and local use

For PC-only use, open `local_simulator.html` in a browser. To run the web relay, use Python 3.12 and run `python3 web_server.py`, then visit `http://127.0.0.1:8080/web`. Phone orientation sensors cannot connect through local HTTP.

This repository is public on GitHub, and the [web app](https://abdominal-ultrasound-simulator.onrender.com/web) is live on Render. Render uses the root `Dockerfile`; the service listens on `PORT` and exposes `/healthz` for health checks. Sessions are stored in a single process's memory, so the current design is intended for one instance during evaluation. Anyone who knows the public URL can open the app; do not enter confidential information.

Run the checks with `python3 -B -m unittest discover -s tests -v`. The browser checks in `tests/test_simulator_html.py` (anatomy-window keys, PC tilt operations, and the layout of the on-screen hints) run only when Playwright and a Chromium-based browser are installed. Without them, all of these browser checks are skipped and only the static checks run.

## Clinical review

The [review checklist](REVIEW_CHECKLIST_JA.md) lists 16 candidate views, the state to record for reproducible review, and unresolved anatomy questions. The reference diagrams are fixed schematics, not ultrasound photographs or pass criteria. Do not use them as confirmed teaching answers until specialist review is complete.

## Related learning tools

- [SonoSim SonoSimulator](https://sonosim.com/virtual-ultrasound-scanning-sonosimulator/) offers case-based ultrasound training with a virtual probe guide.
- [Butterfly ScanLab](https://www.butterflynetwork.com/int/en-uk/education) is an educational app for image acquisition practice with Butterfly hardware.

These links are provided for context. They do not imply affiliation or equivalent clinical validity.

## License

The application is released under the [MIT License](LICENSE). The bundled QR code library has its own [MIT license](vendor/LICENSE-qrcodejs).
