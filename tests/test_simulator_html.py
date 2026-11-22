"""Regression checks for keyboard handlers in local_simulator.html.

The static checks use only the standard library and always run. The browser
check runs only when Playwright and a Chromium-based browser are available;
otherwise it is skipped. Set SIMULATOR_CHROME to a browser executable to use a
specific installation.
"""

import os
import re
import threading
import unittest
from pathlib import Path

import web_server


HTML_PATH = Path(__file__).resolve().parents[1] / 'local_simulator.html'
HTML = HTML_PATH.read_text(encoding='utf-8')

# Names that can be called without being defined in the page itself.
JS_GLOBALS = {
    'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'typeof',
    'Number', 'String', 'Boolean', 'Array', 'Object', 'Set', 'Map', 'Promise',
    'parseFloat', 'parseInt', 'isFinite', 'setTimeout', 'clearTimeout',
    'setInterval', 'clearInterval', 'requestAnimationFrame', 'fetch',
}


def handler_body(anchor):
    """Return the arrow-function body that follows a unique addEventListener anchor."""
    self_check = HTML.count(anchor)
    if self_check != 1:
        raise AssertionError(f'Expected one handler for {anchor!r}, found {self_check}')
    start = HTML.index('{', HTML.index(anchor))
    depth = 0
    for index in range(start, len(HTML)):
        if HTML[index] == '{':
            depth += 1
        elif HTML[index] == '}':
            depth -= 1
            if depth == 0:
                return HTML[start + 1:index]
    raise AssertionError(f'Unclosed handler for {anchor!r}')


def bare_calls(body):
    """Function names called directly, excluding method calls such as e.preventDefault()."""
    return set(re.findall(r'(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(', body)) - JS_GLOBALS


def is_defined(name):
    pattern = rf'(?:function\s+{re.escape(name)}\s*\(|(?:const|let|var)\s+{re.escape(name)}\s*=)'
    return re.search(pattern, HTML) is not None


class VisibleVersionLabelTest(unittest.TestCase):
    """The page shows no fixed version number; internal identifiers may keep old names."""

    def test_no_v43_in_visible_text(self):
        visible = re.sub(r'V43Addon|abdominal_v43_anatomy|v43ScaledOnce', '', HTML)
        self.assertNotRegex(visible, r'(?i)\bv43\b')


class KeyboardHandlerStaticTest(unittest.TestCase):
    HANDLERS = {
        'main keydown': "window.addEventListener('keydown', e => {\n  if (isMobileMode) return;",
        'popup keydown': "popup.addEventListener('keydown', e =>",
        'popup keyup': "popup.addEventListener('keyup', e =>",
    }

    def test_handlers_call_only_defined_functions(self):
        for label, anchor in self.HANDLERS.items():
            with self.subTest(handler=label):
                missing = sorted(name for name in bare_calls(handler_body(anchor)) if not is_defined(name))
                self.assertEqual(missing, [], f'{label} calls undefined functions')

    def test_modified_keys_are_ignored_before_zone_or_position_keys(self):
        for label in ('main keydown', 'popup keydown'):
            with self.subTest(handler=label):
                body = handler_body(self.HANDLERS[label])
                guard = body.find('if (e.altKey || e.ctrlKey || e.metaKey) return;')
                self.assertNotEqual(guard, -1, f'{label} lacks the Alt/Ctrl/Meta guard')
                self.assertLess(guard, body.index('handleZoneNudgeKey(e)'))
                self.assertLess(guard, body.index('stepZone('))


def find_browser():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return None, 'Playwright is not installed'
    candidates = [os.environ.get('SIMULATOR_CHROME'), None, '/usr/bin/google-chrome',
                  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    return [c for c in candidates if c != ''], None


class BrowserTestBase(unittest.TestCase):
    """Starts one headless browser and a local relay server per test class."""

    @classmethod
    def setUpClass(cls):
        candidates, reason = find_browser()
        if candidates is None:
            raise unittest.SkipTest(reason)
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = None
        for executable in candidates:
            if executable is not None and not Path(executable).exists():
                continue
            try:
                options = {'args': ['--no-sandbox']}
                if executable:
                    options['executable_path'] = executable
                cls.browser = cls.playwright.chromium.launch(**options)
                break
            except Exception:
                continue
        if cls.browser is None:
            cls.playwright.stop()
            raise unittest.SkipTest('No launchable Chromium-based browser')
        cls.server = web_server.WebHTTPServer(('127.0.0.1', 0), web_server.WebHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def open_page(self, width=1400, height=900, query=''):
        self.errors = []
        self.context = self.browser.new_context(viewport={'width': width, 'height': height})
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(f'main: {error}'))
        self.page.goto(self.base + '/web' + query)
        self.page.wait_for_function('typeof state === "object" && state.selectedZone === "epigastric"')

    def tearDown(self):
        self.context.close()

    def state(self, expression):
        return self.page.evaluate(expression)


class AnatomyWindowBrowserTest(BrowserTestBase):
    """Drives the anatomy pop-up window in a headless browser."""

    def setUp(self):
        self.open_page()
        with self.context.expect_page() as popup_info:
            self.page.click('#btnSchemata')
        self.popup = popup_info.value
        self.popup.on('pageerror', lambda error: self.errors.append(f'popup: {error}'))
        self.popup.wait_for_load_state()

    def press(self, key):
        self.popup.keyboard.press(key)
        self.popup.wait_for_timeout(60)

    def test_anatomy_window_keys(self):
        self.press('ArrowRight')
        self.assertEqual(self.state('state.selectedZone'), 'subcostal_gb')
        self.press('Space')
        self.assertEqual(self.state('state.selectedZone'), 'right_flank')
        self.press('ArrowLeft')
        self.assertEqual(self.state('state.selectedZone'), 'subcostal_gb')

        x0 = self.state('state.px')
        self.press('Shift+ArrowRight')
        self.assertAlmostEqual(self.state('state.px'), x0 + 0.5)
        self.assertEqual(self.state('state.selectedZone'), 'subcostal_gb')

        self.press('f')
        self.assertTrue(self.state('state.frozen'))
        self.press('f')
        self.assertFalse(self.state('state.frozen'))

        self.popup.keyboard.down('p')
        self.popup.wait_for_timeout(60)
        self.assertTrue(self.state('state.pcPressing'))
        self.popup.keyboard.up('p')
        self.popup.wait_for_timeout(60)
        self.assertFalse(self.state('state.pcPressing'))

        self.page.evaluate('state.yaw = 30; state.pitch = 10; state.roll = -10')
        self.press('r')
        self.assertEqual(self.state('[state.yaw, state.pitch, state.roll]'), [0, 0, 0])
        self.assertEqual(self.errors, [])

    def test_modified_keys_do_not_change_zone_or_position(self):
        before = self.state('[state.selectedZone, state.px, state.py]')
        for key in ('Alt+ArrowRight', 'Control+ArrowRight', 'Meta+ArrowRight',
                    'Alt+Space', 'Alt+Shift+ArrowRight', 'Control+Shift+ArrowDown',
                    'Meta+Shift+ArrowLeft'):
            with self.subTest(key=key):
                self.press(key)
                self.assertEqual(self.state('[state.selectedZone, state.px, state.py]'), before)
        self.assertEqual(self.errors, [])



class EchoTiltBrowserTest(BrowserTestBase):
    """Option (Mac) / Alt (Windows) + drag on the echo image, driven by synthetic input.

    Playwright sends Alt as a modifier to the page. It cannot show whether the
    operating system or browser intercepts the real Option/Alt key.
    """

    def setUp(self):
        self.open_page()
        box = self.page.locator('#echoCanvas').bounding_box()
        self.cx = box['x'] + box['width'] / 2
        self.cy = box['y'] + box['height'] / 2

    def angles(self):
        return self.state('[state.pitch, state.roll]')

    def drag(self, dx, dy, alt=True):
        if alt:
            self.page.keyboard.down('Alt')
        self.page.mouse.move(self.cx, self.cy)
        self.page.mouse.down()
        self.page.mouse.move(self.cx + dx, self.cy + dy, steps=5)
        self.page.mouse.up()
        if alt:
            self.page.keyboard.up('Alt')
        self.page.wait_for_timeout(50)

    def test_directions_follow_the_documented_mapping_and_clamp(self):
        self.drag(0, -40)
        self.assertEqual(self.angles(), [10, 0], 'drag up tilts toward the head (pitch +)')
        self.drag(-40, 0)
        self.assertEqual(self.angles(), [10, 10], 'drag left tilts toward patient right (roll +)')
        self.drag(0, 80)
        self.drag(80, 0)
        self.assertEqual(self.angles(), [-10, -10], 'down = feet, right = patient left')
        self.drag(0, -1000)
        self.assertEqual(self.angles()[0], 45)
        self.assertEqual(self.state("[document.getElementById('valPitch').textContent, state.source]"), ['45°', 'PC MOUSE'])
        self.assertEqual(self.errors, [])

    def test_release_orders(self):
        # Mouse first, then the key: the angle stays where the mouse was released.
        self.page.keyboard.down('Alt')
        self.page.mouse.move(self.cx, self.cy)
        self.page.mouse.down()
        self.page.mouse.move(self.cx, self.cy - 20, steps=4)
        self.page.mouse.up()
        self.page.mouse.move(self.cx, self.cy - 120, steps=4)
        self.assertEqual(self.angles(), [5, 0])
        self.page.keyboard.up('Alt')
        self.assertEqual(self.angles(), [5, 0])

        # Key first, then the mouse: the drag continues until the mouse is released.
        self.page.keyboard.down('Alt')
        self.page.mouse.move(self.cx, self.cy)
        self.page.mouse.down()
        self.page.mouse.move(self.cx, self.cy - 20, steps=4)
        self.page.keyboard.up('Alt')
        self.page.mouse.move(self.cx, self.cy - 40, steps=4)
        self.assertEqual(self.angles(), [15, 0])
        self.page.mouse.up()
        self.page.mouse.move(self.cx, self.cy - 200, steps=4)
        self.assertEqual(self.angles(), [15, 0])
        self.assertFalse(self.state("document.getElementById('echoCanvas').classList.contains('tilt-dragging')"))
        self.assertFalse(self.state("document.getElementById('echoTiltHint').classList.contains('active')"))
        self.assertEqual(self.errors, [])

    def test_keyboard_works_after_a_tilt_drag(self):
        self.drag(-20, -20)
        self.assertEqual(self.angles(), [5, 5])
        x0 = self.state('state.px')
        self.page.keyboard.press('Shift+ArrowRight')
        self.assertAlmostEqual(self.state('state.px'), x0 + 0.5)
        self.page.keyboard.press('f')
        self.assertTrue(self.state('state.frozen'))
        self.page.keyboard.press('f')
        self.assertFalse(self.state('state.frozen'))
        self.page.keyboard.press('ArrowRight')
        self.assertEqual(self.state('state.selectedZone'), 'subcostal_gb')
        self.page.keyboard.press('ArrowLeft')
        self.assertEqual(self.state('state.selectedZone'), 'epigastric')
        self.assertEqual(self.errors, [])

    def test_alt_keyup_default_is_blocked_only_after_a_tilt_drag(self):
        self.page.evaluate("""window.__altUps = [];
            window.addEventListener('keyup', e => { if (e.key === 'Alt') __altUps.push(e.defaultPrevented); });""")
        self.page.keyboard.press('Alt')
        self.drag(0, -20)
        self.page.keyboard.press('Alt')
        self.assertEqual(self.state('__altUps'), [False, True, False])

    def test_plain_drag_does_not_tilt_or_move_and_highlights_the_hint(self):
        before = self.state('[state.pitch, state.roll, state.px, state.py, state.selectedZone]')
        self.drag(-60, -60, alt=False)
        self.assertEqual(self.state('[state.pitch, state.roll, state.px, state.py, state.selectedZone]'), before)
        self.assertTrue(self.state("document.getElementById('echoTiltHint').classList.contains('pulse')"))
        for modifier in ('Control', 'Meta', 'Shift'):
            with self.subTest(modifier=modifier):
                self.page.keyboard.down(modifier)
                self.drag(-60, -60, alt=False)
                self.page.keyboard.up(modifier)
                self.assertEqual(self.state('[state.pitch, state.roll]'), before[:2])
        self.assertEqual(self.errors, [])

    def test_hint_text_language_and_active_state(self):
        hint = self.page.locator('#echoTiltHint')
        self.assertTrue(hint.is_visible())
        text = hint.inner_text()
        for word in ('エコー画像', 'Option', 'Mac', 'Alt', 'Windows', 'ドラッグ', 'スクロール'):
            self.assertIn(word, text)
        self.page.mouse.move(self.cx, self.cy)
        self.page.keyboard.down('Alt')
        self.assertIn('active', hint.get_attribute('class'))
        for word in ('頭側', '尾側', '患者右', '患者左'):
            self.assertIn(word, hint.inner_text())
        self.page.keyboard.up('Alt')
        self.assertNotIn('active', hint.get_attribute('class'))
        self.page.click('#btnLang')
        text = hint.inner_text()
        for word in ('echo image', 'Option', 'Mac', 'Alt', 'Windows', 'drag', 'scroll'):
            self.assertIn(word, text)
        banner = self.page.locator('#modeBanner').inner_text()
        for word in ('region', 'Fine position', 'Tilt', 'echo image', 'Option', 'Alt'):
            self.assertIn(word, banner)
        self.assertEqual(self.errors, [])


class EchoWheelTiltBrowserTest(BrowserTestBase):
    """Option (Mac) / Alt (Windows) + scroll on the echo image.

    Defaults: 0.15 degrees per pixel, at most 3 degrees per wheel event, and the decaying
    tail after a fast swipe (peak >= 120 px per event) is ignored as inertia. Synthetic
    events check the rules; the feel of real trackpads, natural scrolling, Shift+wheel on
    each OS and real momentum need real devices.
    """

    query = ''

    def setUp(self):
        self.open_page(query=self.query)
        box = self.page.locator('#echoCanvas').bounding_box()
        self.page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)

    def angles(self):
        return self.state('[state.pitch, state.roll]')

    def wheel(self, dx, dy, *modifiers):
        for key in modifiers:
            self.page.keyboard.down(key)
        self.page.mouse.wheel(dx, dy)
        self.page.wait_for_timeout(80)
        for key in reversed(modifiers):
            self.page.keyboard.up(key)

    def fire_sequence(self, deltas_y):
        """Dispatch Alt+wheel events back to back, as one gesture."""
        self.page.evaluate("""deltas => {
            for (const deltaY of deltas) {
                echoCanvas.dispatchEvent(new WheelEvent('wheel', { deltaY, altKey: true, cancelable: true }));
            }
        }""", deltas_y)

    def test_alt_scroll_moves_like_dragging_the_image(self):
        self.wheel(0, 10, 'Alt')
        self.assertEqual(self.angles(), [1.5, 0], 'content moves up = drag up = toward the head')
        self.wheel(10, 0, 'Alt')
        self.assertEqual(self.angles(), [1.5, 1.5], 'content moves left = drag left = toward patient right')
        self.wheel(0, -20, 'Alt')
        self.wheel(-20, 0, 'Alt')
        self.assertEqual(self.angles(), [-1.5, -1.5])
        self.assertEqual(self.state('state.source'), 'PC SCROLL')
        self.assertEqual(self.errors, [])

    def test_each_event_is_limited_to_three_degrees_and_angles_clamp(self):
        self.wheel(0, 10000, 'Alt')
        self.assertEqual(self.angles(), [3, 0])
        self.fire_sequence([10000] * 20)
        self.assertEqual(self.angles(), [45, 0])

    def test_line_delta_mode_is_scaled(self):
        self.page.evaluate("""echoCanvas.dispatchEvent(new WheelEvent('wheel',
            { altKey: true, cancelable: true, deltaY: 1, deltaMode: 1 }))""")
        self.assertAlmostEqual(self.angles()[0], 2.4)

    def test_steady_slow_scroll_is_fully_applied(self):
        self.fire_sequence([10, 12, 9, 11, 10, 12, 8, 10])
        self.assertAlmostEqual(self.angles()[0], 82 * 0.15)

    def test_decaying_inertia_after_a_fast_swipe_is_ignored(self):
        self.fire_sequence([60, 100, 150, 135, 120, 105, 90, 75, 60, 45, 30, 15])
        self.assertEqual(self.angles(), [15, 0], 'five events before the decay is detected, 3 degrees each')

    def test_new_finger_movement_after_inertia_tilts_again(self):
        self.fire_sequence([200, 180, 160, 130, 110, 200, 200])
        self.assertEqual(self.angles(), [15, 0])

    def test_inertia_with_repeated_values_is_ignored(self):
        self.fire_sequence([60, 100, 150, 150, 135, 135, 120, 120, 105, 105, 90, 90])
        self.assertEqual(self.angles(), [24, 0])

    def test_intentional_slow_deceleration_is_kept(self):
        self.fire_sequence([100, 90, 80, 70])
        self.assertEqual(self.angles(), [12, 0], 'peak below 120 px: never treated as inertia')
        self.page.wait_for_timeout(350)
        self.fire_sequence([30, 28, 24, 20, 16, 12, 8, 4])
        self.assertAlmostEqual(self.angles()[0], 12 + 18)

    def test_scroll_without_alt_or_with_ctrl_or_meta_does_not_tilt(self):
        self.wheel(0, 100)
        self.wheel(0, 100, 'Control', 'Alt')
        self.wheel(0, 100, 'Meta', 'Alt')
        self.wheel(0, 100, 'Shift')
        self.assertEqual(self.angles(), [0, 0])
        self.assertEqual(self.errors, [])

    def test_shift_alt_wheel_tilts_left_right_in_the_documented_direction(self):
        # Wheel toward the user with Shift = scroll right = content moves left = like dragging left = patient right (+).
        self.wheel(0, 10, 'Alt', 'Shift')
        self.assertEqual(self.angles(), [0, 1.5])
        self.wheel(0, -20, 'Alt', 'Shift')
        self.assertEqual(self.angles(), [0, -1.5])

    def test_shift_fallback_and_horizontal_delta_signs(self):
        fire = """init => echoCanvas.dispatchEvent(new WheelEvent('wheel', { altKey: true, cancelable: true, ...init }))"""
        self.page.evaluate(fire, {'deltaY': 10, 'shiftKey': True})
        self.assertEqual(self.angles(), [0, 1.5], 'Shift with vertical delta only becomes roll, same sign')
        self.page.evaluate(fire, {'deltaY': -20, 'shiftKey': True})
        self.assertEqual(self.angles(), [0, -1.5])
        self.page.wait_for_timeout(350)
        self.page.evaluate(fire, {'deltaX': 20, 'deltaY': 0, 'shiftKey': True})
        self.assertEqual(self.angles(), [0, 1.5], 'a browser-converted horizontal delta is used as is')

    def test_default_scroll_is_blocked_only_for_tilt(self):
        self.page.evaluate("""window.__wheel = [];
            echoCanvas.addEventListener('wheel', e => __wheel.push(e.defaultPrevented));
            window.__altUps = [];
            window.addEventListener('keyup', e => { if (e.key === 'Alt') __altUps.push(e.defaultPrevented); });""")
        self.wheel(0, 10)
        self.wheel(0, 10, 'Alt')
        self.assertEqual(self.state('__wheel'), [False, True])
        self.assertEqual(self.state('__altUps'), [True])

    def test_keyboard_works_after_scroll_tilt(self):
        self.wheel(0, 10, 'Alt')
        x0 = self.state('state.px')
        self.page.keyboard.press('Shift+ArrowRight')
        self.assertAlmostEqual(self.state('state.px'), x0 + 0.5)
        self.page.keyboard.press('ArrowRight')
        self.assertEqual(self.state('state.selectedZone'), 'subcostal_gb')
        self.assertEqual(self.errors, [])


class EchoWheelInertiaKeptBrowserTest(EchoWheelTiltBrowserTest):
    """?wheelInertia=keep applies the decaying tail too (for comparison on real devices)."""

    query = '?wheelInertia=keep'

    def test_decaying_inertia_after_a_fast_swipe_is_ignored(self):
        self.fire_sequence([60, 100, 150, 135, 120, 105, 90, 75, 60, 45, 30, 15])
        self.assertEqual(self.angles(), [35.25, 0])

    def test_new_finger_movement_after_inertia_tilts_again(self):
        self.skipTest('Only meaningful with the inertia filter on')

    def test_inertia_with_repeated_values_is_ignored(self):
        self.skipTest('Only meaningful with the inertia filter on')


class InputDebugBrowserTest(BrowserTestBase):
    """Opt-in measurement panel (?debug=input) and test-only wheel parameters."""

    def wheel_at_center(self, dx, dy, alt=True):
        box = self.page.locator('#echoCanvas').bounding_box()
        self.page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        if alt:
            self.page.keyboard.down('Alt')
        self.page.mouse.wheel(dx, dy)
        self.page.wait_for_timeout(80)
        if alt:
            self.page.keyboard.up('Alt')

    def test_debug_panel_is_absent_by_default(self):
        self.open_page()
        self.assertEqual(self.page.locator('#inputDebugPanel').count(), 0)

    def test_debug_panel_reports_a_gesture_and_wheel_params(self):
        self.open_page(query='?debug=input&wheelTilt=0.2&wheelMaxDeg=10')
        panel = self.page.locator('#inputDebugPanel')
        self.assertIn('wheelTilt=0.2°/px  max=10°/event  inertia ignored after peak≥120px', panel.inner_text())
        box = self.page.locator('#echoCanvas').bounding_box()
        self.page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        self.page.keyboard.down('Alt')
        self.page.mouse.wheel(0, 50)
        self.page.mouse.wheel(0, 50)
        self.page.wait_for_timeout(80)
        self.page.keyboard.up('Alt')
        self.assertEqual(self.state('state.pitch'), 20)
        self.page.wait_for_timeout(350)
        self.wheel_at_center(0, 40, alt=False)
        text = panel.inner_text()
        self.assertIn('#2 events 1 (Option/Alt 0, none 1)', text)
        self.assertIn('#1 events 2 (Option/Alt 2, none 0)', text)
        self.assertIn('sum ΔX +0.0  ΔY +100.0 px  max|Δ| 50.0  capped 0  inertia 0', text)
        self.assertIn('angle P +20.0°', text)
        self.assertEqual(self.errors, [])

    def test_debug_panel_counts_ignored_inertia(self):
        self.open_page(query='?debug=input')
        self.page.evaluate("""() => {
            for (const deltaY of [60, 100, 150, 135, 120, 105, 90, 75, 60, 45, 30, 15]) {
                echoCanvas.dispatchEvent(new WheelEvent('wheel', { deltaY, altKey: true, cancelable: true }));
            }
        }""")
        text = self.page.locator('#inputDebugPanel').inner_text()
        self.assertIn('events 12 (Option/Alt 12, none 0)', text)
        self.assertIn('inertia 7', text)
        self.assertIn('angle P +15.0°', text)

    def test_inertia_peak_param(self):
        self.open_page(query='?wheelInertiaPeak=50')
        self.page.evaluate("""() => { for (const deltaY of [100, 90, 80, 70])
            echoCanvas.dispatchEvent(new WheelEvent('wheel', { deltaY, altKey: true, cancelable: true })); }""")
        self.assertEqual(self.state('state.pitch'), 9)

    def test_invalid_wheel_params_fall_back_to_defaults(self):
        for query, delta, expected in (('?wheelTilt=abc', 10, 1.5), ('?wheelTilt=0', 10, 1.5), ('?wheelTilt=5', 10, 1.5),
                                       ('?wheelMaxDeg=0', 100, 3), ('?wheelMaxDeg=50', 100, 3), ('?wheelMaxDeg=x', 100, 3)):
            with self.subTest(query=query):
                self.open_page(query=query)
                self.wheel_at_center(0, delta)
                self.assertEqual(self.state('state.pitch'), expected)
                self.context.close()
        self.context = self.browser.new_context()


class EchoTiltHintLayoutTest(BrowserTestBase):
    """The tilt hint, the caution label and the organ legend under the echo image must not overlap.

    Checked for all five regions, Japanese and English, with and without Option/Alt held
    (the hint switches to the direction guide), at three common window sizes and just
    below and above the width where the caution label moves to the right. The legend
    wraps to several lines in some of these cases.
    """

    CAUTION_BREAKPOINT = 980  # .right-panel container width in @container (max-width: 980px)

    def boxes(self):
        return self.page.evaluate("""() => {
            const box = id => {
                const el = document.getElementById(id);
                if (!el || getComputedStyle(el).display === 'none') return null;
                const r = el.getBoundingClientRect();
                return r.width && r.height ? { x: r.left, y: r.top, w: r.width, h: r.height } : null;
            };
            const p = document.querySelector('.right-panel').getBoundingClientRect();
            return { hint: box('echoTiltHint'), caution: box('viewStatus'), legend: box('organLegend'),
                     panel: { x: p.left, y: p.top, w: p.width, h: p.height },
                     active: document.getElementById('echoTiltHint').classList.contains('active') };
        }""")

    @staticmethod
    def overlap(a, b):
        if not a or not b:
            return False
        return not (a['x'] + a['w'] <= b['x'] or b['x'] + b['w'] <= a['x'] or
                    a['y'] + a['h'] <= b['y'] or b['y'] + b['h'] <= a['y'])

    def check_layout(self, b):
        self.assertIsNotNone(b['hint'])
        self.assertIsNotNone(b['legend'])
        for first, second in (('hint', 'caution'), ('hint', 'legend'), ('caution', 'legend')):
            self.assertFalse(self.overlap(b[first], b[second]), f'{first} overlaps {second}: {b}')
        for name in ('hint', 'caution', 'legend'):
            if b[name]:
                self.assertGreaterEqual(b[name]['x'], b['panel']['x'])
                self.assertGreaterEqual(b[name]['y'], b['panel']['y'])
                self.assertLessEqual(b[name]['x'] + b[name]['w'], b['panel']['x'] + b['panel']['w'])
                self.assertLessEqual(b[name]['y'] + b[name]['h'], b['panel']['y'] + b['panel']['h'])

    def breakpoint_sizes(self):
        self.open_page(1400, 900)
        panel_width = self.page.evaluate("document.querySelector('.right-panel').clientWidth")
        self.context.close()
        offset = 1400 - panel_width
        return [(self.CAUTION_BREAKPOINT + offset - 10, 800), (self.CAUTION_BREAKPOINT + offset + 10, 800)]

    def test_hint_caution_and_legend_do_not_overlap(self):
        multiline_cases = 0
        sizes = [(1400, 900), (1280, 720), (1024, 700)] + self.breakpoint_sizes()
        for width, height in sizes:
            for query in ('', '?lang=en'):
                self.open_page(width, height, query)
                box = self.page.locator('#echoCanvas').bounding_box()
                self.page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                for zone in range(5):
                    for alt in (False, True):
                        with self.subTest(size=f'{width}x{height}', query=query, zone=zone, alt=alt):
                            if alt:
                                self.page.keyboard.down('Alt')
                            self.page.wait_for_timeout(120)
                            b = self.boxes()
                            self.assertEqual(b['active'], alt)
                            self.check_layout(b)
                            if b['legend']['h'] > 36:
                                multiline_cases += 1
                            if alt:
                                self.page.keyboard.up('Alt')
                    self.page.keyboard.press('ArrowRight')
                self.assertEqual(self.errors, [])
                self.context.close()
        self.context = self.browser.new_context()
        self.assertGreater(multiline_cases, 0, 'expected at least one case with a multi-line legend')

    def test_caution_moves_right_below_the_breakpoint(self):
        below, above = self.breakpoint_sizes()
        positions = []
        for width, height in (below, above):
            self.open_page(width, height)
            positions.append(self.page.evaluate("getComputedStyle(document.getElementById('viewStatus')).transform"))
            self.context.close()
        self.context = self.browser.new_context()
        self.assertEqual(positions[0], 'none', 'narrow panel: caution aligned right, no centering transform')
        self.assertNotEqual(positions[1], 'none', 'wide panel: caution centered with translateX(-50%)')


if __name__ == '__main__':
    unittest.main()
