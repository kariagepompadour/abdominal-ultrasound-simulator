# 腹部エコーシミュレーター

[English](README.md) · [Web版を開く](https://abdominal-ultrasound-simulator.onrender.com/web)

腹部エコーのプローブの当て方・傾け方を練習するための教育用の試作です（実験中）。標準では、実在の成人1名の腹部CTから作られた公開・匿名化済みのアトラス（SPL Abdominal Atlas。改変版、[解剖データ](#解剖データ)を参照）の組織ラベルからエコー像を計算します。アトラスにラベルのない肝内の構造（中・左肝静脈、門脈の枝、胆管、肝円索）は、教本の断層模式図に沿うように手で追加しました。教本の6断面の位置では模式図どおりの像を出し、プローブを傾けたり動かしたりすると実CTの解剖の像へ移ります。CT画像そのものや個人を特定できる情報は含みません。正常エコーの正解集や診断用ソフトウェアではありません。解剖は1名分で、教本の典型的な解剖と異なる部分があります。各観察見本との一致は専門医による検証前です。

## 使い方

1. PCで[Web版](https://abdominal-ultrasound-simulator.onrender.com/web)を開き、心窩部、右季肋部、右肋間、右側腹部、左側腹部、下腹部から接触部位を選びます。画面の描画は各PCのブラウザで実行されます。
   - **教本の断面（肝）**：①〜⑥のボタンを押すと、腹部超音波の教本の肝の断層模式図6枚（心窩部横走査、心窩部横〜右肋骨弓下走査、右肋間走査、縦走査の大動脈面・下大静脈面2面）と同じ位置・角度にプローブが置かれ、模式図どおりの配置のエコー像が出ます。この位置では、教本の模式図の構造の配置をそのまま使った像（シェーマ準拠の断面像）を表示し、プローブを傾けたり動かしたりすると、実CTの解剖の像へ少しずつ移ります。左の欄に見本図と所見の一覧を表示し、今の画面に出ている所見に ✓ を付けます。「頭側へ傾ける」などのボタンで、教本の走査法に書かれた傾け方の画像（実CTの解剖）に切り替えられます。教本の図や写真は収録していません。
   - **視野**：標準は腹部用コンベックス探触子の実寸（曲率半径50 mm・視野角70°）です。上部の「視野」ボタンで、教本の写真のように浅い所が広い視野に切り替えられます。
   - **速さ**：遅いPCでは、走査線の数を自動で半分にします。最初からそうするには `?quality=low` を付けます。
   - **解剖**：URLの末尾に `?anatomy=model` を付けると、実CTの代わりに以前の簡略化した3Dモデルを使います。下腹部（膀胱）はCTの範囲外のため、常に簡略化したモデルです。
2. PCだけで次の操作ができます（スマホは不要です）。
   - **部位の切替**：`←` / `→` または `Space`
   - **接触位置の微調整**：`Shift`＋矢印（0.5 cmずつ、選んだ部位の±1.5 cm以内）、またはボディマークのドラッグ
   - **回転**：`Q` で反時計回り、`E` で時計回り（ボディマーク上の向き。1回5°、押し続けると連続、±90°まで）。Yawスライダーでも同じ角度を変えられます。
   - **チルト**：右側の**エコー画像の上で**、Macは `Option`、Windowsは `Alt` を押しながらマウスでドラッグします。上＝頭側、下＝尾側、左＝患者右、右＝患者左へビームを傾け、マウスを離すとその角度で止まります。ドラッグを始めた後は、キーを先に離してもマウスを離すまでチルトが続きます。同じキーを押しながら、トラックパッドの2本指スクロールやマウスホイールでも傾けられます。向きは画像をスクロールで動かす向き（同じ向きへのドラッグ）と同じで、マウスホイールで左右に傾けるときは `Shift` も押します。キーを押している間は、エコー画像左下の案内が方向表示に変わります。Pitch / Rollスライダーでも同じ角度を変えられます。
   - **その他**：`F` はFREEZE、`R` は基準画像に戻す、`P` 長押しは圧迫です。
3. スマホを使う場合だけ「スマホ接続 (QR)」を開きます。スマホに表示された確認番号をPCと照合し、PCで承認してください。QRだけでは操作を開始できません。PC操作を始めると角度はPC側で保持され、スマホ上半分で新しい探索を始めるとスマホ側へ戻ります。

スマホ接続にはHTTPSと姿勢センサー対応ブラウザが必要です。Renderの無料インスタンスは休止後の初回応答が遅くなることがあります。ページの再読み込みやサーバー再起動後はQRを作り直してください。接続セッションはサーバーのメモリに保持され、画像と3D描画は各PC内で生成されます。

## 公開中のWeb版とローカル実行

PCのみで試すには `local_simulator.html` をブラウザで開けます。Web中継を試すには、Python 3.12で `python3 web_server.py` を実行し、`http://127.0.0.1:8080/web` を開きます。ローカルHTTPからスマホの姿勢センサーには接続できません。

このリポジトリはGitHubで公開中で、[Web版](https://abdominal-ultrasound-simulator.onrender.com/web)はRenderで稼働中です。Renderではルートの `Dockerfile` を使用し、`PORT` で指定されたポートで待ち受け、`/healthz` をヘルスチェックに使います。接続情報は単一プロセスのメモリ内にあるため、現状は1インスタンスでの試験運用を前提とします。公開URLは知っている人が閲覧できます。機密情報を入力しないでください。

テストは `python3 -B -m unittest discover -s tests -v` で実行します。`tests/test_simulator_html.py` のブラウザ確認（解剖シェーマ別窓のキー操作、PCのチルト操作、画面案内の配置）は、PlaywrightとChromium系ブラウザがある環境でだけ実行します。ない環境ではこれらのブラウザ確認をすべて省略し、静的な確認だけを実行します。

## 専門医による確認

[監修チェックリスト](REVIEW_CHECKLIST_JA.md)に、16の観察候補、再現条件として記録する項目、未検証の解剖表現をまとめています。観察見本は固定の模式図で、実際のエコー写真や到達判定ではありません。確認結果が得られるまで、教育上の正解として使わないでください。

## 関連する学習ツール

- [SonoSim SonoSimulator](https://sonosim.com/virtual-ultrasound-scanning-sonosimulator/)：仮想プローブとケースを使う超音波トレーニング製品。
- [Butterfly ScanLab](https://www.butterflynetwork.com/int/en-uk/education)：実機と連携した画像取得練習を提供する教育アプリ。

これらは比較のための紹介です。本プロジェクトとの提携や同等の医学的妥当性を意味しません。

## 解剖データ

実CTの解剖は **SPL Abdominal Atlas** から作りました：Talos IF, Jakab M, Kikinis R. *CT-based Atlas of the Abdomen* (SPL Abdominal Atlas). Surgical Planning Laboratory, Brigham and Women's Hospital, Harvard Medical School, 2015（[Open Anatomy](https://www.openanatomy.org/)）。3D Slicer License で配布されています。全文は [data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt](data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt) にあります。

**これは改変版です。** アトラスのラベルをエコー用の組織の分類にまとめ直し、ラベルのない組織はCT値から分類し（脂肪・空気・造影された血液）、範囲の切り出し・境界の平滑化・標準的な成人の大きさへの縮尺を行い、肝内の血管をアプリ内で追加しました。CT画像の濃度そのものは配布していません。アトラスの作成者と所属機関は、このアプリを確認・推奨していません。ライセンスのとおり、研究・教育用であり、臨床には使えません。実CTの解剖を使っている間は、操作欄の下に出典とライセンス全文へのリンクを表示します。アトラスからデータを作る手順は、開発用フォルダの `tools/atlas/` にあります（Web版の配布物には含めません）。

<details>
<summary>3D Slicer License の全文（ライセンスの条件により、利用者向けの文書にも全文を載せています）</summary>

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

## ライセンス

本体は [MIT License](LICENSE) です。QR生成ライブラリは別の [MITライセンス](vendor/LICENSE-qrcodejs) に従います。解剖データは [3D Slicer License](data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt) に従います。
