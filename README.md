# Abdominal Ultrasound Simulator

[日本語](README_JA.md) · [Open the web app](https://abdominal-ultrasound-simulator.onrender.com/web)

An educational prototype for practising where to place and how to tilt an abdominal ultrasound probe (experimental). By default the echo is computed from real human anatomy: tissue labels derived from a public, de-identified abdominal CT atlas of one adult (SPL Abdominal Atlas, modified; see [Anatomy data](#anatomy-data)). Intrahepatic structures that the atlas does not label (hepatic veins, portal branches, bile ducts, liver segments) come from BodyParts3D, a reference 3D human model, deformed to fit the CT liver; only the ligamentum teres, the common bile duct and the main pancreatic duct were added by hand (the ducts follow the shape of the CT pancreas and are drawn only inside fat or the pancreas). At 16 standard views (liver 6, spleen 2, biliary 4, pancreas 4) the image follows a section schema of that view; tilting or moving the probe changes it to the real-CT anatomy. The app contains no CT images or identifiable patient data, does not establish normal ultrasound appearances, and does not provide diagnostic guidance. The anatomy is one person's and differs from typical anatomy in places; correspondence with reference views has not been validated by a specialist.

## Use

1. Open the [web app](https://abdominal-ultrasound-simulator.onrender.com/web) on a PC and choose the epigastric, right subcostal, right intercostal, right flank, or left flank region. The lower abdomen (bladder, pelvis) is not included: it is usually examined by urology or gynaecology rather than in routine abdominal screening. Rendering runs in each PC's browser.
   - **Standard views**: choose an organ (liver, spleen, biliary, pancreas), then a view. Each button places the probe at the position and angle of a standard section used in abdominal ultrasound screening: liver 6 (epigastric transverse, epigastric-to-right-subcostal, right intercostal, and longitudinal aorta and IVC planes), spleen 2 (left intercostal, longitudinal), biliary 4 (epigastric-to-right-subcostal, right subcostal, longitudinal, right intercostal) and pancreas 4 (head and body–tail, transverse and longitudinal). At that position the echo uses the layout of the section schema (a schema-based section image); tilting or moving the probe gradually changes to the real-CT anatomy. The strip below the echo shows how many of the findings of the view are in the current image. “Open Anatomy Window” opens on its “Standard view” tab with the scanning notes, the tilt steps, a reference drawing and a findings checklist that marks what is in the current image; the main window's left panel and body mark stay as they are. For the liver and biliary tract, step buttons in that tab such as “Tilt cranially” switch to the standard tilts of that view; where a schema of that tilt is available (umbilical portion, the five right-intercostal tilts, caudate and ligamentum teres planes; for the biliary tract, the CBD in the pancreatic head and the hepatic hilum) the image follows it, otherwise it shows the real-CT anatomy. The schemas are the app's own drawings; no figures or photos from published materials are included.
   - **Field of view**: the default is the actual size of an abdominal convex probe (50 mm radius, 70°). The “View” button switches to a trapezoid field with a wider near field.
   - **Speed**: on a slow PC the app automatically halves the number of scan lines; add `?quality=low` to start that way.
   - **Anatomy**: add `?anatomy=model` to the URL to use the earlier simplified 3D model instead of the real-CT anatomy.
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

## Anatomy data

The real-CT anatomy is derived from the **SPL Abdominal Atlas**: Talos IF, Jakab M, Kikinis R. *CT-based Atlas of the Abdomen* (SPL Abdominal Atlas). Surgical Planning Laboratory, Brigham and Women's Hospital, Harvard Medical School, 2015 ([Open Anatomy](https://www.openanatomy.org/)). It is distributed under the 3D Slicer License; the full text is in [data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt](data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt).

**This is a modified version.** The atlas labels were regrouped into ultrasound tissue classes, unlabeled tissue was classified from CT values (fat, air, contrast-filled blood), the volume was cropped, smoothed and rescaled to a typical adult size, and intrahepatic vessels were added in the app. No CT image intensities are distributed. The atlas authors and their institutions have not reviewed or endorsed this app. As the license states, the data are for research and education only and are not for clinical use. While the real-CT anatomy is in use, the app shows this source and a link to the full license below the controls. The steps that build the data from the atlas are in `tools/atlas/` of the development folder (not part of the web package).

<details>
<summary>Full text of the 3D Slicer License (the license requires it in the user documentation)</summary>

```text
All or portions of this licensed product (such portions are the "Software") have been obtained
under license from The Brigham and Women's Hospital, Inc. and are subject to the following terms
and conditions:


For more information, please see:

                      https://www.slicer.org

The 3D Slicer license below is a BSD style license, with extensions
to cover contributions and other issues specific to 3D Slicer.


3D Slicer Contribution and Software License Agreement ("Agreement")
Version 1.0 (December 20, 2005)

This Agreement covers contributions to and downloads from the 3D
Slicer project ("Slicer") maintained by The Brigham and Women's
Hospital, Inc. ("Brigham"). Part A of this Agreement applies to
contributions of software and/or data to Slicer (including making
revisions of or additions to code and/or data already in Slicer). Part
B of this Agreement applies to downloads of software and/or data from
Slicer. Part C of this Agreement applies to all transactions with
Slicer. If you distribute Software (as defined below) downloaded from
Slicer, all of the paragraphs of Part B of this Agreement must be
included with and apply to such Software.

Your contribution of software and/or data to Slicer (including prior
to the date of the first publication of this Agreement, each a
"Contribution") and/or downloading, copying, modifying, displaying,
distributing or use of any software and/or data from Slicer
(collectively, the "Software") constitutes acceptance of all of the
terms and conditions of this Agreement. If you do not agree to such
terms and conditions, you have no right to contribute your
Contribution, or to download, copy, modify, display, distribute or use
the Software.

PART A. CONTRIBUTION AGREEMENT - License to Brigham with Right to
Sublicense ("Contribution Agreement").

1. As used in this Contribution Agreement, "you" means the individual
   contributing the Contribution to Slicer and the institution or
   entity which employs or is otherwise affiliated with such
   individual in connection with such Contribution.

2. This Contribution Agreement applies to all Contributions made to
   Slicer, including without limitation Contributions made prior to
   the date of first publication of this Agreement. If at any time you
   make a Contribution to Slicer, you represent that (i) you are
   legally authorized and entitled to make such Contribution and to
   grant all licenses granted in this Contribution Agreement with
   respect to such Contribution; (ii) if your Contribution includes
   any patient data, all such data is de-identified in accordance with
   U.S. confidentiality and security laws and requirements, including
   but not limited to the Health Insurance Portability and
   Accountability Act (HIPAA) and its regulations, and your disclosure
   of such data for the purposes contemplated by this Agreement is
   properly authorized and in compliance with all applicable laws and
   regulations; and (iii) you have preserved in the Contribution all
   applicable attributions, copyright notices and licenses for any
   third party software or data included in the Contribution.

3. Except for the licenses granted in this Agreement, you reserve all
   right, title and interest in your Contribution.

4. You hereby grant to Brigham, with the right to sublicense, a
   perpetual, worldwide, non-exclusive, no charge, royalty-free,
   irrevocable license to use, reproduce, make derivative works of,
   display and distribute the Contribution. If your Contribution is
   protected by patent, you hereby grant to Brigham, with the right to
   sublicense, a perpetual, worldwide, non-exclusive, no-charge,
   royalty-free, irrevocable license under your interest in patent
   rights covering the Contribution, to make, have made, use, sell and
   otherwise transfer your Contribution, alone or in combination with
   any other code.

5. You acknowledge and agree that Brigham may incorporate your
   Contribution into Slicer and may make Slicer available to members
   of the public on an open source basis under terms substantially in
   accordance with the Software License set forth in Part B of this
   Agreement. You further acknowledge and agree that Brigham shall
   have no liability arising in connection with claims resulting from
   your breach of any of the terms of this Agreement.

6. YOU WARRANT THAT TO THE BEST OF YOUR KNOWLEDGE YOUR CONTRIBUTION
   DOES NOT CONTAIN ANY CODE THAT REQUIRES OR PRESCRIBES AN "OPEN
   SOURCE LICENSE" FOR DERIVATIVE WORKS (by way of non-limiting
   example, the GNU General Public License or other so-called
   "reciprocal" license that requires any derived work to be licensed
   under the GNU General Public License or other "open source
   license").

PART B. DOWNLOADING AGREEMENT - License from Brigham with Right to
Sublicense ("Software License").

1. As used in this Software License, "you" means the individual
   downloading and/or using, reproducing, modifying, displaying and/or
   distributing the Software and the institution or entity which
   employs or is otherwise affiliated with such individual in
   connection therewith. The Brigham and Women's Hospital,
   Inc. ("Brigham") hereby grants you, with right to sublicense, with
   respect to Brigham's rights in the software, and data, if any,
   which is the subject of this Software License (collectively, the
   "Software"), a royalty-free, non-exclusive license to use,
   reproduce, make derivative works of, display and distribute the
   Software, provided that:

(a) you accept and adhere to all of the terms and conditions of this
Software License;

(b) in connection with any copy of or sublicense of all or any portion
of the Software, all of the terms and conditions in this Software
License shall appear in and shall apply to such copy and such
sublicense, including without limitation all source and executable
forms and on any user documentation, prefaced with the following
words: "All or portions of this licensed product (such portions are
the "Software") have been obtained under license from The Brigham and
Women's Hospital, Inc. and are subject to the following terms and
conditions:"

(c) you preserve and maintain all applicable attributions, copyright
notices and licenses included in or applicable to the Software;

(d) modified versions of the Software must be clearly identified and
marked as such, and must not be misrepresented as being the original
Software; and

(e) you consider making, but are under no obligation to make, the
source code of any of your modifications to the Software freely
available to others on an open source basis.

2. The license granted in this Software License includes without
   limitation the right to (i) incorporate the Software into
   proprietary programs (subject to any restrictions applicable to
   such programs), (ii) add your own copyright statement to your
   modifications of the Software, and (iii) provide additional or
   different license terms and conditions in your sublicenses of
   modifications of the Software; provided that in each case your use,
   reproduction or distribution of such modifications otherwise
   complies with the conditions stated in this Software License.

3. This Software License does not grant any rights with respect to
   third party software, except those rights that Brigham has been
   authorized by a third party to grant to you, and accordingly you
   are solely responsible for (i) obtaining any permissions from third
   parties that you need to use, reproduce, make derivative works of,
   display and distribute the Software, and (ii) informing your
   sublicensees, including without limitation your end-users, of their
   obligations to secure any such required permissions.

4. The Software has been designed for research purposes only and has
   not been reviewed or approved by the Food and Drug Administration
   or by any other agency. YOU ACKNOWLEDGE AND AGREE THAT CLINICAL
   APPLICATIONS ARE NEITHER RECOMMENDED NOR ADVISED. Any
   commercialization of the Software is at the sole risk of the party
   or parties engaged in such commercialization. You further agree to
   use, reproduce, make derivative works of, display and distribute
   the Software in compliance with all applicable governmental laws,
   regulations and orders, including without limitation those relating
   to export and import control.

5. The Software is provided "AS IS" and neither Brigham nor any
   contributor to the software (each a "Contributor") shall have any
   obligation to provide maintenance, support, updates, enhancements
   or modifications thereto. BRIGHAM AND ALL CONTRIBUTORS SPECIFICALLY
   DISCLAIM ALL EXPRESS AND IMPLIED WARRANTIES OF ANY KIND INCLUDING,
   BUT NOT LIMITED TO, ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR
   A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL
   BRIGHAM OR ANY CONTRIBUTOR BE LIABLE TO ANY PARTY FOR DIRECT,
   INDIRECT, SPECIAL, INCIDENTAL, EXEMPLARY OR CONSEQUENTIAL DAMAGES
   HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY ARISING IN ANY WAY
   RELATED TO THE SOFTWARE, EVEN IF BRIGHAM OR ANY CONTRIBUTOR HAS
   BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. TO THE MAXIMUM
   EXTENT NOT PROHIBITED BY LAW OR REGULATION, YOU FURTHER ASSUME ALL
   LIABILITY FOR YOUR USE, REPRODUCTION, MAKING OF DERIVATIVE WORKS,
   DISPLAY, LICENSE OR DISTRIBUTION OF THE SOFTWARE AND AGREE TO
   INDEMNIFY AND HOLD HARMLESS BRIGHAM AND ALL CONTRIBUTORS FROM AND
   AGAINST ANY AND ALL CLAIMS, SUITS, ACTIONS, DEMANDS AND JUDGMENTS
   ARISING THEREFROM.

6. None of the names, logos or trademarks of Brigham or any of
   Brigham's affiliates or any of the Contributors, or any funding
   agency, may be used to endorse or promote products produced in
   whole or in part by operation of the Software or derived from or
   based on the Software without specific prior written permission
   from the applicable party.

7. Any use, reproduction or distribution of the Software which is not
   in accordance with this Software License shall automatically revoke
   all rights granted to you under this Software License and render
   Paragraphs 1 and 2 of this Software License null and void.

8. This Software License does not grant any rights in or to any
   intellectual property owned by Brigham or any Contributor except
   those rights expressly granted hereunder.

PART C. MISCELLANEOUS

This Agreement shall be governed by and construed in accordance with
the laws of The Commonwealth of Massachusetts without regard to
principles of conflicts of law. This Agreement shall supercede and
replace any license terms that you may have agreed to previously with
respect to Slicer.
```

</details>

The intrahepatic vessels, bile ducts and liver segments are derived from **BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International** ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)). The meshes were deformed to fit the CT liver, reduced to centre lines and given minimum widths for ultrasound; see [data/bodyparts3d/LICENSE-BODYPARTS3D.txt](data/bodyparts3d/LICENSE-BODYPARTS3D.txt) for the changes. DBCLS has not reviewed or endorsed this app.

## License

The application is released under the [MIT License](LICENSE). The bundled QR code library has its own [MIT license](vendor/LICENSE-qrcodejs). The anatomy data follow the [3D Slicer License](data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt) and, for the BodyParts3D-derived data, [CC BY 4.0](data/bodyparts3d/LICENSE-BODYPARTS3D.txt).
