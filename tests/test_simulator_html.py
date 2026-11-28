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
        # 既存のテストは模式モデル（?anatomy=model）で行う。実CTのテストは AtlasAnatomyTest で別に行う。
        if 'anatomy=' not in query:
            query = query + '&anatomy=model' if query.startswith('?') else '?anatomy=model' + query
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
        self.assertEqual(self.state('state.selectedZone'), 'right_intercostal')
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


class YawKeyBrowserTest(BrowserTestBase):
    """Q / E rotate the probe (yaw) by 5 degrees, from the main window and the anatomy window."""

    def setUp(self):
        self.open_page()
        self.page.click('#appTitle')

    def yaw(self):
        return self.state('state.yaw')

    def test_q_and_e_rotate_in_steps_and_clamp(self):
        self.page.keyboard.press('e')
        self.assertEqual(self.yaw(), 5, 'E = clockwise on the body marker (yaw +)')
        self.page.keyboard.press('q')
        self.page.keyboard.press('q')
        self.assertEqual(self.yaw(), -5)
        self.page.keyboard.press('Shift+E')
        self.assertEqual(self.yaw(), 0, 'upper case (Shift or Caps Lock) works the same')
        for _ in range(25):
            self.page.keyboard.press('e')
        self.assertEqual(self.yaw(), 90)
        self.assertEqual(self.state("[document.getElementById('valYaw').textContent, state.source]"), ['90°', 'PC KEY'])
        self.page.keyboard.press('r')
        self.assertEqual(self.yaw(), 0, 'R returns to the reference view')
        self.assertEqual(self.errors, [])

    def test_held_key_repeats(self):
        self.page.keyboard.down('e')
        self.page.evaluate("""() => { for (let i = 0; i < 3; i++)
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'e', repeat: true, cancelable: true })); }""")
        self.page.keyboard.up('e')
        self.assertEqual(self.yaw(), 20)

    def test_modified_q_e_do_nothing_and_zone_keys_are_unchanged(self):
        for key in ('Alt+e', 'Control+e', 'Meta+e', 'Alt+q'):
            with self.subTest(key=key):
                self.page.keyboard.press(key)
                self.assertEqual(self.yaw(), 0)
        self.page.keyboard.press('e')
        self.page.keyboard.press('Shift+ArrowRight')
        self.assertEqual(self.yaw(), 5)
        self.page.keyboard.press('ArrowRight')
        self.assertEqual(self.state('state.selectedZone'), 'subcostal_gb')
        self.assertEqual(self.errors, [])

    def test_rotation_unfreezes_and_works_from_the_anatomy_window(self):
        self.page.keyboard.press('f')
        self.assertTrue(self.state('state.frozen'))
        self.page.keyboard.press('e')
        self.assertFalse(self.state('state.frozen'))
        with self.context.expect_page() as popup_info:
            self.page.click('#btnSchemata')
        popup = popup_info.value
        popup.wait_for_load_state()
        popup.keyboard.press('q')
        popup.keyboard.press('q')
        popup.wait_for_timeout(60)
        self.assertEqual(self.yaw(), -5)
        self.assertEqual(self.errors, [])

    def test_guides_mention_the_rotation_keys(self):
        for query, words in (('', ('回転', 'Q', 'E')), ('?lang=en', ('Rotate', 'Q', 'E'))):
            with self.subTest(query=query):
                self.context.close()
                self.open_page(query=query)
                banner = self.page.locator('#modeBanner').inner_text()
                guide = self.page.locator('#ruleBox').inner_text()
                for word in words:
                    self.assertIn(word, banner)
                    self.assertIn(word, guide)


class BodyMarkPositionTest(BrowserTestBase):
    """Probe marker positions on the body mark (display only; echo images use the 3D model).

    Body-mark drawing coordinates: costal arch apex (xiphoid) about y=47-55, lateral ends of the
    costal arch at (80, 99) and (206, 99), umbilicus at (143, 158).
    """

    def setUp(self):
        self.open_page()

    def marker(self):
        return self.state('bodyMarkFromModel(state.px, state.py)')

    def select(self, zone):
        self.page.evaluate(f"selectZone('{zone}')")
        self.page.wait_for_timeout(100)

    @staticmethod
    def right_costal_margin_y(x):
        return 49 + (132 - x) * 50 / 52

    def test_epigastric_marker_is_just_below_the_xiphoid_inside_the_costal_arch(self):
        self.select('epigastric')
        x, y = self.marker()
        self.assertGreater(y - 5, 55, 'below the xiphoid notch')
        self.assertLess(y, 99, 'above the lateral ends of the costal arch')
        self.assertLess(y, (55 + 158) / 2, 'closer to the xiphoid than to the umbilicus')
        self.assertGreater(x - 18, 132 - (y - 49) * 52 / 50, 'inside the right costal line')
        self.assertLess(x + 18, 154 + (y - 49) * 52 / 50, 'inside the left costal line')

    def test_right_subcostal_marker_is_below_the_right_costal_margin_and_caudal_to_epigastric(self):
        self.select('epigastric')
        epigastric_y = self.marker()[1]
        self.select('subcostal_gb')
        x, y = self.marker()
        self.assertLess(x, 143, 'patient right side')
        self.assertGreater(y - 5, self.right_costal_margin_y(x - 18), 'whole marker below the right costal margin')
        self.assertGreater(y, epigastric_y, 'epigastric is cranial to the right subcostal position')

    def test_flank_markers_are_at_the_lateral_costal_arch_level_and_caudal_to_epigastric(self):
        self.select('epigastric')
        epigastric_y = self.marker()[1]
        for zone, side in (('right_flank', -1), ('left_flank', 1)):
            with self.subTest(zone=zone):
                self.select(zone)
                x, y = self.marker()
                self.assertEqual((x > 143) - (x < 143), side)
                self.assertLessEqual(abs(y - 99), 12, 'near the lateral end of the costal arch (y = 99)')
                self.assertGreater(y, epigastric_y)

    def test_lower_abdomen_is_not_offered(self):
        # 下腹部（膀胱）は消化器のルーチン検査ではなく、実CTの範囲外なので選べない
        self.assertEqual(self.page.locator('#btnPreBladder').count(), 0)
        self.assertNotIn('pelvis_bladder', self.state('ZONE_ORDER'))

    def test_nudge_moves_marker_by_the_same_scale_and_round_trips(self):
        for zone in ('epigastric', 'subcostal_gb', 'right_intercostal', 'right_flank', 'left_flank'):
            with self.subTest(zone=zone):
                self.select(zone)
                x0, y0 = self.marker()
                self.page.keyboard.press('Shift+ArrowUp')
                x1, y1 = self.marker()
                self.assertAlmostEqual(x1, x0)
                self.assertAlmostEqual(y1, y0 - 0.5 * 8.5)
                back = self.state('modelFromBodyMark(...bodyMarkFromModel(state.px, state.py))')
                now = self.state('[state.px, state.py]')
                self.assertAlmostEqual(back[0], now[0])
                self.assertAlmostEqual(back[1], now[1])

    def test_pressing_on_the_drawn_marker_does_not_move_the_probe(self):
        for zone in ('epigastric', 'subcostal_gb', 'right_flank', 'left_flank'):
            with self.subTest(zone=zone):
                self.select(zone)
                before = self.state('[state.px, state.py]')
                x, y = self.marker()
                box = self.page.locator('#bodyCanvas').bounding_box()
                self.page.mouse.move(box['x'] + x / 286 * box['width'], box['y'] + y / 240 * box['height'])
                self.page.mouse.down()
                self.page.mouse.up()
                after = self.state('[state.px, state.py]')
                # Mouse positions are rounded to whole CSS pixels (about 0.12 cm on the body mark).
                self.assertAlmostEqual(after[0], before[0], delta=0.2)
                self.assertAlmostEqual(after[1], before[1], delta=0.2)
        self.assertEqual(self.errors, [])


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




class TextbookViewTest(BrowserTestBase):
    """Textbook standard sections (liver, textbook pp.10-17).

    At each textbook position and angle the echo follows the textbook section schema (SCHEMA_SCENES);
    away from it the image moves to the 3D model. Counts and positions come from
    textbookFindingCounts(): the current image without breathing motion on a 160 x 120 grid.
    "lateral" is image-left (-) / image-right (+) in cm, "depth" is the distance from the skin in cm.
    """

    MIN_SAMPLES = 12   # about 0.2 cm2: a 5 mm vessel in cross-section is visible

    def setUp(self):
        self.open_page()

    def counts(self, view, step='base'):
        return self.page.evaluate(f"() => {{ selectTextbookView('{view}', '{step}'); return textbookFindingCounts(); }}")

    def visible(self, counts, finding):
        fids = self.page.evaluate(f"findingFids('{finding}')")
        # 主膵管（正常は径 2 mm 以下）は細い線・点にしか見えないので基準を下げる（アプリの findingMinSamples と同じ考え方）
        return any(counts.get(fid, {}).get('n', 0) >= (5 if fid == 'pd' else self.MIN_SAMPLES) for fid in fids)

    def assert_layout(self, view, relations):
        c = self.counts(view)
        for a, rel, b in relations:
            with self.subTest(view=view, relation=f'{a} {rel} {b}'):
                key = 'lateral' if rel == 'left of' else 'depth'
                self.assertLess(c[a][key], c[b][key])

    def test_section_schemas_of_the_textbook_for_liver_spleen_biliary_and_pancreas(self):
        # 教本の「断層模式図」のページ：肝 p.10–11（6枚）、脾 p.43（2枚）、胆道 p.52–53（4枚）、膵 p.72–73（4枚）
        self.assertEqual(self.page.evaluate("TEXTBOOK_ORDER"),
                         ['liver_hv', 'liver_pv', 'liver_ic', 'liver_ao_long', 'liver_ivc_s4', 'liver_ivc_rl',
                          'spl_ic', 'spl_long', 'bil_ep', 'bil_sc', 'bil_long', 'bil_ic',
                          'pan_head', 'pan_headlong', 'pan_body', 'pan_bodylong',
                          'ren_r_long', 'ren_l_long', 'ren_hilum', 'vas_pv', 'vas_ce', 'vas_sv'])
        self.assertEqual(self.page.evaluate("TEXTBOOK_ORDER.filter(id => SCHEMA_SCENES[id]).length"), 22)
        organs = self.page.evaluate("Object.fromEntries(TEXTBOOK_ORGANS.map(o => [o.id, TEXTBOOK_ORDER.filter(id => TEXTBOOK_VIEWS[id].organ === o.id).length]))")
        self.assertEqual(organs, {'liver': 6, 'spleen': 2, 'biliary': 4, 'pancreas': 4, 'renal': 3, 'vessels': 3})
        # 大血管の列は脈管の走査のコツの A〜F：A・B・D は肝の断面を共有する
        self.assertEqual(self.page.evaluate("organViews('vessels').map(v => v.id)"),
                         ['liver_ao_long', 'liver_ivc_rl', 'vas_pv', 'liver_hv', 'vas_ce', 'vas_sv'])
        # 教本名を出さないので、教本のページも画面には出さない（ソースのコメントにだけ残す）
        self.assertEqual(self.page.evaluate("TEXTBOOK_ORDER.filter(id => 'pages' in TEXTBOOK_VIEWS[id])"), [])
        notes = self.page.evaluate("TEXTBOOK_ORDER.flatMap(id => TEXTBOOK_VIEWS[id].steps.flatMap(s => [s.noteJa, s.noteEn]))")
        self.assertEqual([n for n in notes if re.search(r'\bp\.\s?\d', n) or '教本' in n], [])
        missing = self.page.evaluate("TEXTBOOK_ORDER.flatMap(id => TEXTBOOK_VIEWS[id].steps.flatMap(s => s.findings.filter(f => !FINDING_DEFS[f])))")
        self.assertEqual(missing, [])

    def test_textbook_toolbar_groups_the_views_by_organ(self):
        self.assertEqual(self.page.locator('#textbookOrganButtons button').count(), 6)
        self.assertEqual(self.page.locator('#textbookViewButtons button').count(), 6)
        self.page.click('#btnOrgan_pancreas')
        self.assertEqual(self.page.locator('#textbookViewButtons button').count(), 4)
        # 臓器のボタンは、その臓器の最初の断面を押したのと同じ
        self.assertEqual(self.state('[state.textbookView, activeSchema().id]'), ['pan_head', 'pan_head'])
        self.assertTrue(self.page.locator('#btnTextbook_pan_head').evaluate("b => b.classList.contains('active')"))
        self.page.click('#btnTextbook_pan_body')
        self.assertEqual(self.state('[state.textbookView, state.selectedZone, activeSchema().id, activeSchema().w]'), ['pan_body', 'epigastric', 'pan_body', 1])
        self.assertTrue(self.page.locator('#btnOrgan_pancreas').evaluate("b => b.classList.contains('active')"))
        self.page.click('#btnOrgan_pancreas')   # 同じ臓器のボタンを押しても、選んでいる断面は変わらない
        self.assertEqual(self.state('state.textbookView'), 'pan_body')
        self.page.click('#btnOrgan_spleen')
        self.assertEqual(self.state('[state.textbookView, state.selectedZone]'), ['spl_ic', 'left_flank'])
        self.page.click('#btnTextbook_spl_long')
        self.assertEqual(self.state('state.textbookView'), 'spl_long')
        # 大血管：A を押すと肝④と同じ断面。列は大血管のまま
        self.page.click('#btnOrgan_vessels')
        self.assertEqual(self.state('state.textbookView'), 'liver_ao_long')
        self.assertEqual(self.page.locator('#textbookViewButtons button').count(), 6)
        self.assertIn('A', self.page.text_content('#btnTextbook_liver_ao_long'))
        self.page.click('#btnTextbook_liver_hv')
        self.assertTrue(self.page.locator('#btnOrgan_vessels').evaluate("b => b.classList.contains('active')"))
        self.page.click('#btnOrgan_liver')
        self.assertEqual(self.state('state.textbookView'), 'liver_hv')   # 肝の列にもある断面なのでそのまま
        self.assertIn('①', self.page.text_content('#btnTextbook_liver_hv'))
        self.page.click('#btnLang')
        self.assertIn('Standard views', self.page.text_content('#textbookToolbarLabel'))
        self.assertEqual(self.page.text_content('#btnOrgan_spleen'), 'Spleen')
        self.assertEqual(self.errors, [])

    def test_every_step_shows_all_of_its_textbook_findings(self):
        views = self.page.evaluate("TEXTBOOK_ORDER.map(id => [id, TEXTBOOK_VIEWS[id].steps.map(s => [s.id, s.findings])])")
        for view, steps in views:
            for step, findings in steps:
                with self.subTest(view=view, step=step):
                    counts = self.counts(view, step)
                    missing = [f for f in findings if not self.visible(counts, f)]
                    self.assertEqual(missing, [])
        self.assertEqual(self.errors, [])

    def test_textbook_position_shows_the_schema_and_leaving_it_moves_to_the_3d_model(self):
        self.page.evaluate("selectTextbookView('liver_ic')")
        self.assertEqual(self.state('activeSchema().w'), 1)
        self.page.evaluate("state.yaw += 5")
        w = self.state('activeSchema().w')
        self.assertTrue(0 < w < 1, w)
        self.page.evaluate("state.yaw += 15")
        self.assertIsNone(self.state('activeSchema()'))
        # 傾けの段階（教本の走査法の写真）は3Dモデルで描く。
        self.page.evaluate("selectTextbookView('liver_pv', 'head')")
        self.assertIsNone(self.state('activeSchema()'))

    def test_hepatic_vein_plane_layout(self):
        # 教本 p.10「心窩部横走査」：画面左から RHV・MHV・LHV、IVC の左（画面右）に Ao、その背側に椎体。
        self.assert_layout('liver_hv', [
            ('rhv', 'left of', 'ivc'), ('mhv', 'left of', 'lhv'), ('ivc', 'left of', 'ao'),
            ('mhv', 'above', 'ivc'), ('ivc', 'above', 'spine'),
            ('S8', 'left of', 'S4'), ('S5', 'left of', 'S4'), ('S4', 'left of', 'S3'), ('S4', 'left of', 'S2'),
            ('S5', 'above', 'S8'), ('S3', 'above', 'S2')])

    def test_portal_branch_plane_layout(self):
        # 教本 p.10「心窩部横走査〜右肋骨弓下走査」
        self.assert_layout('liver_pv', [
            ('rpv', 'left of', 'lpvTrans'), ('lpvTrans', 'left of', 'lpvUmb'), ('ligTeres', 'above', 'lpvUmb'),
            ('lpvTrans', 'above', 'S1'), ('S1', 'above', 'ivc'), ('ivc', 'left of', 'ao'), ('rhv', 'left of', 'ivc'),
            ('p3', 'above', 'p2'), ('rpv', 'above', 'rpvPost'), ('S5', 'above', 'S6'), ('S6', 'left of', 'S7')])

    def test_right_intercostal_layout(self):
        # 教本 p.10「右肋間走査」：画面左＝頭側。IVC は画面下を横に走る。
        self.assert_layout('liver_ic', [
            ('S8', 'left of', 'S5'), ('S7', 'left of', 'S6'), ('S8', 'above', 'S7'), ('S5', 'above', 'S6'),
            ('rhv', 'above', 'ivc'), ('rpv', 'above', 'ivc'), ('p8', 'left of', 'p5'), ('rhv', 'left of', 'gb')])
        c = self.counts('liver_ic')
        self.assertGreater(c['ivc']['n'], 500, 'IVC seen along its length')

    def test_aorta_long_layout(self):
        # 教本 p.11「縦走査（大動脈面）」：画面左＝頭側。
        self.assert_layout('liver_ao_long', [
            ('eso', 'left of', 'ce'), ('ce', 'left of', 'sma'), ('cha', 'left of', 'sa'),
            ('stomach', 'above', 'pancBody'), ('pancBody', 'above', 'sv'), ('ce', 'above', 'ao'), ('S3', 'above', 'S2'),
            ('ao', 'above', 'spine')])

    def test_ivc_plane_s4_border_layout(self):
        # 教本 p.11「縦走査（下大静脈面）：S4 と外側区との境界面」
        self.assert_layout('liver_ivc_s4', [
            ('lpvUmb', 'left of', 'pv'), ('ligTeres', 'above', 'pv'), ('pha', 'above', 'pv'), ('pv', 'above', 'ivc'),
            ('S1', 'above', 'ivc'), ('ivc', 'above', 'rra'), ('lhv', 'left of', 'S1'), ('pv', 'left of', 'pancHead')])

    def test_ivc_plane_lobe_border_layout(self):
        # 教本 p.11「縦走査（下大静脈面）：右葉と左葉の境界面」
        self.assert_layout('liver_ivc_rl', [
            ('mhv', 'left of', 'gb'), ('gb', 'above', 'pv'), ('cbd', 'above', 'pv'), ('pv', 'above', 'ivc'),
            ('pv', 'left of', 'pancHead'), ('S1', 'above', 'ivc')])

    def test_intercostal_probe_avoids_rib_shadows_and_rotation_across_ribs_shows_them(self):
        for step in ('base', 'post', 'ant'):
            with self.subTest(step=step):
                self.assertNotIn('rib', self.counts('liver_ic', step))
        crossed = self.page.evaluate("() => { selectTextbookView('liver_ic'); state.yaw = -40; return textbookFindingCounts(); }")
        self.assertGreater(crossed.get('rib', {}).get('n', 0), 100)

    def test_field_of_view_switch(self):
        self.assertEqual(self.state('[probeGeometryMode, PROBE_RADIUS_CM, PROBE_HALF_ANGLE_DEG]'), ['textbook', 24, 17])
        self.page.click('#btnFov')
        self.assertEqual(self.state('[probeGeometryMode, PROBE_RADIUS_CM, PROBE_HALF_ANGLE_DEG]'), ['convex', 5, 35])
        self.assertIn('コンベックス', self.page.text_content('#btnFov'))
        self.page.click('#btnFov')
        self.assertEqual(self.state('probeGeometryMode'), 'textbook')
        self.assertEqual(self.errors, [])

    def test_textbook_notes_steps_schema_and_findings_are_in_the_anatomy_window(self):
        self.page.evaluate("selectTextbookView('liver_pv')")
        self.page.wait_for_timeout(900)
        total = self.page.evaluate("TEXTBOOK_VIEWS.liver_pv.steps[0].findings.length")
        # メイン画面：左の列は通常どおり（操作案内とボディマークの位置は変わらない）、ツールバーに所見の数と段階のボタン
        self.assertTrue(self.page.locator('#modeBanner').is_visible())
        self.assertEqual(self.page.locator('#textbookPanel').count(), 0)
        legend = self.page.text_content('#organLegend')   # エコーの下の帯：所見の数と、傾けの段階を選べる場所
        self.assertIn(f'この断面の所見 {total} / {total}', legend)
        self.assertNotIn('教本', legend)   # 教本名を出さないので、教本のページも公開画面には出さない
        self.assertIn('解剖シェーマを別画面で見る', legend)
        self.assertTrue(self.page.locator('#btnTextbook_liver_pv').evaluate("b => b.classList.contains('active')"))
        # 別画面：教本の断面タブに説明・見本図・所見の一覧
        with self.page.expect_popup() as info:
            self.page.click('#btnSchemata')
        popup = info.value
        popup.wait_for_timeout(600)
        self.assertTrue(popup.locator('button[data-kind="textbook"]').evaluate("b => b.classList.contains('active')"))
        self.assertNotIn('教本', popup.locator('body').inner_text())
        self.assertIn('門脈', popup.text_content('#tbNote'))
        self.assertEqual(popup.locator('#tbFindings li').count(), total)
        self.assertEqual(popup.locator('#tbFindings li.seen').count(), total)
        self.assertEqual(popup.text_content('#tbScore'), f'✓ {total} / {total}')
        self.assertFalse(popup.locator('#diagramGrid').is_visible())
        # 段階のボタンは別画面からも押せる
        popup.locator('#tbSteps button', has_text='頭側へ傾ける').click()
        self.page.wait_for_timeout(900)
        self.assertEqual(self.state('[state.pitch, state.textbookStep]'), [35, 'head'])
        popup.wait_for_timeout(300)
        self.assertIn('中肝静脈', popup.text_content('#tbFindings'))
        # 別の断面を選ぶと、別画面もその断面に変わる
        self.page.click('#btnOrgan_pancreas')
        self.page.click('#btnTextbook_pan_body')
        popup.wait_for_timeout(500)
        self.assertIn('膵-3', popup.text_content('#tbTitle'))
        popup.locator('button[data-kind="section"]').click()
        popup.wait_for_timeout(300)
        self.assertTrue(popup.locator('#diagramGrid').is_visible())
        self.assertFalse(popup.locator('#textbookDetail').is_visible())
        self.assertEqual(self.errors, [])

    def test_anatomy_window_follows_a_language_switch(self):
        self.page.evaluate("selectTextbookView('liver_ic', 'ant')")
        with self.page.expect_popup() as info:
            self.page.click('#btnSchemata')
        popup = info.value
        popup.wait_for_timeout(600)
        self.assertIn('さらに内側へ傾ける', popup.text_content('#tbSteps'))
        self.assertIn('前区域枝', popup.text_content('#tbFindings'))
        self.page.click('#btnLang')
        popup.wait_for_timeout(700)
        self.assertIn('Tilt further inward', popup.text_content('#tbSteps'))
        self.assertIn('Right anterior branch', popup.text_content('#tbFindings'))
        self.assertIn('Tilting further inward', popup.text_content('#tbNote'))
        self.assertIn('Standard view', popup.text_content('button[data-kind="textbook"]'))
        self.page.click('#btnLang')
        popup.wait_for_timeout(700)
        self.assertIn('さらに内側へ傾ける', popup.text_content('#tbSteps'))
        self.assertEqual(self.errors, [])

    def test_zone_selection_leaves_the_textbook_view(self):
        self.page.evaluate("selectTextbookView('liver_hv')")
        self.page.keyboard.press('ArrowRight')
        self.page.wait_for_timeout(100)
        self.assertIsNone(self.state('state.textbookView'))
        self.assertEqual(self.state('[state.yaw, state.pitch, state.roll]'), [0, 0, 0])

    def test_reset_returns_to_the_step_pose_and_phone_angles_are_relative_to_it(self):
        self.page.evaluate("selectTextbookView('liver_pv')")
        self.page.evaluate("state.yaw = 10; state.pitch = 0; state.roll = -20")
        self.page.keyboard.press('r')
        self.page.wait_for_timeout(100)
        self.assertEqual(self.state('[state.yaw, state.pitch, state.roll]'), [-16, 27, 2])
        self.page.evaluate("ingestProbePacket('PHONE', {px: 0, py: 0, yaw: 4, pitch: -5, roll: 1, exploring: 1})")
        self.assertEqual(self.state('[state.yaw, state.pitch, state.roll]'), [-12, 22, 3])

    def test_body_mark_shows_the_textbook_probe_sites(self):
        def marker(view):
            return self.page.evaluate(f"() => {{ selectTextbookView('{view}'); return bodyMarkFromModel(state.px, state.py); }}")
        x, y = marker('liver_hv')
        self.assertTrue(55 < y < 80 and abs(x - 143) < 10, 'just below the xiphoid')
        x, y = marker('liver_pv')
        self.assertLess(x, 143)
        self.assertGreater(y, 49 + (132 - x) * 50 / 52, 'below the right costal margin')
        x, y = marker('liver_ic')
        self.assertLess(x, 85, 'right lateral chest wall')
        self.assertLess(y, 99)
        for view in ('liver_ao_long', 'liver_ivc_s4', 'liver_ivc_rl'):
            with self.subTest(view=view):
                x, y = marker(view)
                self.assertTrue(55 < y < 90 and abs(x - 143) < 12, 'epigastrium, longitudinal')
                self.assertEqual(self.state('state.yaw'), 90)

    def test_english_labels(self):
        self.page.evaluate("toggleLang(); selectTextbookView('liver_ivc_rl')")
        self.assertIn('Long.', self.page.text_content('#btnTextbook_liver_ivc_rl'))
        self.assertIn('Standard views', self.page.text_content('#textbookToolbarLabel'))
        self.assertEqual(self.errors, [])


class AtlasAnatomyTest(BrowserTestBase):
    """Real-CT anatomy (SPL Abdominal Atlas, modified) with the textbook sections.

    The textbook section schema is shown at each textbook position; tilting away from it shows the real CT,
    where the hand-placed intrahepatic vessels (hepatic veins, portal branches) lie in the textbook planes.
    """

    MIN_SAMPLES = 12

    def open_atlas(self, query='?anatomy=atlas'):
        self.open_page(query=query)
        for _ in range(100):
            if self.page.evaluate('() => ATLAS.ready || ATLAS.failed'):
                break
            self.page.wait_for_timeout(100)
        self.assertTrue(self.page.evaluate('ATLAS.ready'))

    def visible(self, counts, finding):
        fids = self.page.evaluate(f"findingFids('{finding}')")
        # 主膵管（正常は径 2 mm 以下）は細い線・点にしか見えないので基準を下げる（アプリの findingMinSamples と同じ考え方）
        return any(counts.get(fid, {}).get('n', 0) >= (5 if fid == 'pd' else self.MIN_SAMPLES) for fid in fids)

    def counts(self, view, step='base'):
        # 実CTでは、肋骨・ガスの音響陰影に隠れたものは「見えた」に数えない
        return self.page.evaluate(f"() => {{ selectTextbookView('{view}', '{step}'); return textbookFindingCounts(true); }}")

    def test_real_ct_is_loaded_and_used_with_a_real_convex_probe(self):
        self.open_atlas()
        self.assertTrue(self.page.evaluate('atlasReady()'))
        self.assertEqual(self.page.evaluate('probeGeometryMode'), 'convex')
        self.assertEqual(self.page.evaluate('ZONE_STARTS.epigastric'), [-0.5, 3.0])
        self.page.wait_for_timeout(300)
        self.assertTrue(self.page.evaluate('realisticEcho'))
        # 出典とライセンス全文への案内（3D Slicer License：利用者向けの表示）
        credit = self.page.locator('#dataCredit')
        self.assertTrue(credit.is_visible())
        self.assertIn('SPL Abdominal Atlas', credit.inner_text())
        self.assertEqual(credit.locator('a').first.get_attribute('href'), 'data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt')
        # 肝内の血管・胆管・区域は BodyParts3D（CC BY 4.0、指定の表記）
        self.assertTrue(self.page.evaluate('ATLAS.bodyParts3d'))
        self.assertIn('BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International', credit.inner_text())
        self.assertEqual(self.errors, [])

    def test_every_textbook_step_shows_all_of_its_findings_on_real_ct(self):
        self.open_atlas()
        views = self.page.evaluate("TEXTBOOK_ORDER.map(id => [id, TEXTBOOK_VIEWS[id].steps.map(s => [s.id, s.findings])])")
        for view, steps in views:
            for step, findings in steps:
                with self.subTest(view=view, step=step):
                    counts = self.counts(view, step)
                    self.assertEqual([f for f in findings if not self.visible(counts, f)], [])

    def test_real_ct_has_the_main_pancreatic_duct_and_the_cbd_in_the_pancreatic_head(self):
        # 実CTには膵管・膵内総胆管のラベルがないので中心線を置いた。標準断面の定位置の実CTの像（シェーマなし）にも出る。
        self.open_atlas('?anatomy=atlas&schema=off')
        for view, fids in (('pan_head', ['pd', 'cbd']), ('pan_body', ['pd', 'cbd']), ('pan_headlong', ['cbd']), ('bil_long', ['cbd'])):
            counts = self.page.evaluate(f"() => {{ selectTextbookView('{view}'); return textbookFindingCounts(true); }}")
            for fid in fids:
                with self.subTest(view=view, fid=fid):
                    # 主膵管は正常の太さ（径 2 mm 以下）なので細い線にしか見えない：数え方の基準を下げる
                    self.assertGreaterEqual(counts.get(fid, {}).get('n', 0), 5 if fid == 'pd' else 12)
        # 主膵管は膵の中だけ、総胆管は十二指腸・門脈のラベルの中には描かない
        outside = self.page.evaluate('''() => {
          const bad = [];
          for (const seg of ATLAS_VESSEL_SEGMENTS) {
            if (seg.path.fid !== 'pd' && seg.path.fid !== 'cbd') continue;
            for (let t = 0; t <= 1; t += 0.25) {
              const p = seg.start.map((v, k) => v + seg.delta[k] * t), c = atlasClass(...p), v = atlasSample(...p);
              if (v.fid === seg.path.fid && (seg.path.fid === 'pd' ? c !== 12 : [19, 22, 32].includes(c))) bad.push([seg.path.fid, c]);
            }
          }
          return bad; }''')
        self.assertEqual(outside, [])
        self.assertEqual(self.errors, [])

    def test_real_ct_kidney_has_cortex_medulla_and_arcuate_dots(self):
        # 実CTの腎には皮質・髄質の区別がないので、腎の表面からの深さで錐体（低エコー）と弓状動脈を描く
        self.open_atlas('?anatomy=atlas&schema=off')
        for view, kidney_fid in (('ren_r_long', 'rk'), ('ren_l_long', 'lk'), ('ren_hilum', 'rk')):
            counts = self.page.evaluate(f"() => {{ selectTextbookView('{view}'); return textbookFindingCounts(true); }}")
            with self.subTest(view=view):
                self.assertGreaterEqual(counts.get('medulla', {}).get('n', 0), 12)
                self.assertGreaterEqual(counts.get('arcuate', {}).get('n', 0), 5)
                kidney = counts.get(kidney_fid, {}).get('n', 0) + counts.get('medulla', {}).get('n', 0)
                self.assertGreater(counts.get(kidney_fid, {}).get('n', 0), 0.2 * kidney)   # 皮質も残る
        # 弓状動脈は皮質と髄質の境（腎の表面から 0.6〜0.78 cm）だけに出る。皮質の表層・髄質の奥には出ない。
        depths = self.page.evaluate("""() => {
          const { NI, NJ, NK, vx, vy, vz, midI, xiphoidK, skinJ } = ATLAS, out = [];
          for (let k = 0; k < NK; k++) for (let j = 0; j < NJ; j += 2) for (let i = 0; i < NI; i += 2) {
            const c = ATLAS.data[(k * NJ + j) * NI + i];
            if (c !== 13 && c !== 14) continue;
            const s = kidneyParenchymaLook((i - midI) * vx, (k - xiphoidK) * vy, (skinJ - j) * vz, c);
            if (s.fid === 'arcuate') out.push(ATLAS.kidneyDepth[(k * NJ + j) * NI + i] * 0.05);
          }
          return out; }""")
        self.assertGreater(len(depths), 20)
        self.assertTrue(all(0.55 <= d <= 0.8 for d in depths), (min(depths), max(depths)))
        self.assertEqual(self.page.evaluate("ZONE_PROBE_BASES.right_flank.lateral"), True)
        self.assertEqual(self.errors, [])

    def test_real_ct_separates_smv_left_renal_vessels_and_psoas(self):
        # SPL に最初から分かれて入っているラベル（atlas/split_labels.py で分け直した）
        self.open_atlas('?anatomy=atlas&schema=off')
        counts = self.page.evaluate("() => { selectTextbookView('pan_head'); return textbookFindingCounts(true); }")
        for fid in ('smv', 'sma', 'lrv', 'lra', 'ao'):
            with self.subTest(fid=fid):
                self.assertGreaterEqual(counts.get(fid, {}).get('n', 0), 12)
        # 左腎静脈は大動脈と上腸間膜動脈の間（深さで大動脈より浅く、上腸間膜動脈より深い）
        self.assertLess(counts['sma']['depth'], counts['lrv']['depth'])
        self.assertLess(counts['lrv']['depth'], counts['ao']['depth'])
        # 上腸間膜静脈は門脈より尾側、腸腰筋は右腎の縦走査で腎の背側
        y = self.page.evaluate("""() => {
          const { data, NI, NJ, NK, vy, xiphoidK } = ATLAS, ys = { 32: [], 51: [] };
          for (let k = 0; k < NK; k++) for (let j = 0; j < NJ; j++) for (let i = 0; i < NI; i++) {
            const c = data[(k * NJ + j) * NI + i]; if (c === 32 || c === 51) ys[c].push((k - xiphoidK) * vy);
          }
          const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
          return [mean(ys[32]), mean(ys[51])]; }""")
        self.assertLess(y[0] + 2, y[1])
        counts = self.page.evaluate("() => { selectTextbookView('ren_r_long'); return textbookFindingCounts(true); }")
        self.assertGreaterEqual(counts.get('psoas', {}).get('n', 0), 12)
        self.assertEqual(self.errors, [])

    def test_real_ct_has_lung_duodenum_and_esophagus_from_totalsegmentator(self):
        # TotalSegmentator で同じCTから取った構造（atlas/ts_overlay.py）
        self.open_atlas('?anatomy=atlas&schema=off')
        for view, fid in (('spl_ic', 'lungGas'), ('pan_head', 'duod'), ('vas_pv', 'duodBulb'), ('liver_ao_long', 'eso')):
            counts = self.page.evaluate(f"() => {{ selectTextbookView('{view}'); return textbookFindingCounts(true); }}")
            with self.subTest(view=view, fid=fid):
                self.assertGreaterEqual(counts.get(fid, {}).get('n', 0), 12)
        # 肺：胸膜の奥は多重反射（胸膜までの距離ごとの横線）だけで、肺の奥の臓器は見えない
        self.assertEqual(self.page.evaluate("[lungReverb(6, 3).val > 100, lungReverb(4.5, 3).val < 50, lungReverb(3.05, 3).val > 200]"), [True, True, True])
        classes = self.page.evaluate("() => { const s = new Set(ATLAS.data); return [7, 8, 24, 26, 28].map(c => s.has(c)); }")
        self.assertEqual(classes, [True, True, True, True, True])
        self.assertEqual(self.errors, [])

    def test_spleen_views_use_a_probe_on_the_left_side_of_the_body(self):
        self.open_atlas()
        self.page.evaluate("selectTextbookView('spl_ic')")
        self.assertEqual(self.state('ZONE_PROBE_BASES.left_flank.side'), 'left')
        origin = self.state('probeOrigin()')
        self.assertGreater(origin[0], 5)            # 患者の左（x が正）の体表
        frame = self.state('currentProbeFrame()')
        self.assertLess(frame['bx'], -0.5)          # 左の側面から体の中（右）へ向かう
        self.page.evaluate("state.yaw += 20")       # 定位置から外れると実CTの脾が見える
        counts = self.page.evaluate("textbookFindingCounts(true)")
        self.assertGreaterEqual(counts.get('spleen', {}).get('n', 0), 12)
        self.assertEqual(self.errors, [])

    def test_tilt_steps_without_a_textbook_schema_are_drawn_from_the_real_ct(self):
        # 教本の走査法のページに写真とシェーマの組がない段階（肝② 頭側・尾側）は実CTの像
        self.open_atlas()
        for view, step in (('liver_pv', 'head'), ('liver_pv', 'foot')):
            with self.subTest(view=view, step=step):
                self.page.evaluate(f"selectTextbookView('{view}', '{step}')")
                self.assertIsNone(self.page.evaluate('activeSchema()'))

    def test_tilt_steps_with_a_textbook_schema_follow_that_schema(self):
        # 走査法のページ（p.12・p.14–15・p.17）の写真とシェーマの組から作った段階は、その段階のシェーマどおりの像
        self.open_atlas()
        steps = (('liver_hv', 'umb'), ('liver_ic', 'postOuter'), ('liver_ic', 'post'), ('liver_ic', 'antTrunk'),
                 ('liver_ic', 'ant'), ('liver_ic', 'rhv'), ('liver_ivc_s4', 'caudate'), ('liver_ivc_s4', 'teres'))
        for view, step in steps:
            with self.subTest(view=view, step=step):
                self.page.evaluate(f"selectTextbookView('{view}', '{step}')")
                self.assertEqual(self.page.evaluate('[activeSchema().id, activeSchema().w]'), [f'{view}:{step}', 1])
        # 段階のあいだでは、近い方の段階のシェーマに移る
        self.page.evaluate("selectTextbookView('liver_ic', 'base')")
        self.assertEqual(self.page.evaluate('activeSchema().id'), 'liver_ic')
        self.page.evaluate("state.roll = TEXTBOOK_VIEWS.liver_ic.steps.find(s => s.id === 'post').pose.roll - 1; state.pitch = TEXTBOOK_VIEWS.liver_ic.steps.find(s => s.id === 'post').pose.pitch; state.yaw = TEXTBOOK_VIEWS.liver_ic.steps.find(s => s.id === 'post').pose.yaw")
        self.assertEqual(self.page.evaluate('activeSchema().id'), 'liver_ic:post')
        self.assertEqual(self.errors, [])

    def test_hepatic_vein_plane_of_the_real_ct_matches_the_textbook_layout(self):
        # 教本 p.10「心窩部横走査」：シェーマなし（実CTと肝静脈の配置）でも、RHV・MHV・LHV が IVC へ流入し、Ao・椎体が並ぶ。
        self.open_atlas('?anatomy=atlas&schema=off')
        c = self.counts('liver_hv')
        for finding in ('rhv', 'mhv', 'lhv', 'ivc', 'ao', 'spine'):
            with self.subTest(finding=finding):
                self.assertTrue(self.visible(c, finding))
        for a, rel, b in (('rhv', 'left of', 'ivc'), ('mhv', 'left of', 'lhv'), ('ivc', 'left of', 'ao'),
                          ('mhv', 'above', 'ivc'), ('ivc', 'above', 'spine')):
            with self.subTest(relation=f'{a} {rel} {b}'):
                key = 'lateral' if rel == 'left of' else 'depth'
                self.assertLess(c[a][key], c[b][key])

    def test_leaving_the_textbook_section_keeps_the_real_anatomy_continuous(self):
        self.open_atlas()
        self.page.evaluate("selectTextbookView('liver_hv')")
        self.assertEqual(self.page.evaluate('activeSchema().w'), 1)
        for pitch in (1, 3, 6, 9, 12):
            c = self.page.evaluate(f"() => {{ state.pitch = TEXTBOOK_VIEWS.liver_hv.steps[0].pose.pitch + {pitch}; return textbookFindingCounts(true); }}")
            with self.subTest(pitch=pitch):
                self.assertTrue(self.visible(c, 'ivc'))
                if pitch <= 3:
                    self.assertTrue(self.visible(c, 'ao'))
        self.assertIsNone(self.page.evaluate('activeSchema()'))

    def test_heart_and_contrast_filled_arteries_are_not_drawn_as_bone(self):
        # 動脈相CTの造影血液（心腔・動脈）は高吸収でも骨ではない（以前は骨と判定して音響陰影が出ていた）。
        self.open_atlas()
        n = self.page.evaluate("""() => { const c = {}; for (let x = -3; x <= 4; x += 0.25) for (let y = -1.8; y <= 0; y += 0.3) for (let z = 4; z <= 11; z += 0.25) {
            const k = atlasClass(x, y, z); c[k] = (c[k] || 0) + 1; } return c; }""")
        self.assertGreater(n.get('23', 0), 200)
        self.assertLess(n.get('4', 0), 10)

    def test_model_mode_keeps_the_textbook_photo_view_and_model_positions(self):
        self.open_page(query='?anatomy=model')
        self.assertEqual(self.page.evaluate('probeGeometryMode'), 'textbook')
        self.assertFalse(self.page.evaluate('atlasReady()'))
        self.assertFalse(self.page.locator('#dataCredit').is_visible())

    def test_missing_atlas_data_falls_back_to_the_schematic_model(self):
        # 読み込みに失敗（file:// で開いた、データがない・壊れている）しても、模式モデルと教本の写真の視野で動く。
        for status in (404, 'broken'):
            with self.subTest(status=status):
                self.errors = []
                self.context = self.browser.new_context(viewport={'width': 1400, 'height': 900})
                self.page = self.context.new_page()
                self.page.on('pageerror', lambda error: self.errors.append(f'main: {error}'))
                if status == 404:
                    self.page.route('**/data/spl-abdominal-atlas/**', lambda route: route.fulfill(status=404, body='missing'))
                else:
                    self.page.route('**/abdomen_labels.u8.gz', lambda route: route.fulfill(status=200, body=b'not gzip'))
                self.page.goto(self.base + '/web?anatomy=atlas')
                for _ in range(100):
                    if self.page.evaluate('() => ATLAS.ready || ATLAS.failed'):
                        break
                    self.page.wait_for_timeout(100)
                self.page.wait_for_timeout(200)
                self.assertTrue(self.page.evaluate('ATLAS.failed'))
                self.assertFalse(self.page.evaluate('atlasReady()'))
                self.assertEqual(self.page.evaluate('probeGeometryMode'), 'textbook')
                self.assertEqual(self.page.evaluate('ZONE_STARTS.epigastric'), [-0.6, 1.7])
                counts = self.page.evaluate("() => { selectTextbookView('liver_hv'); return textbookFindingCounts(); }")
                self.assertTrue(self.visible(counts, 'ivc'))
                self.assertEqual(self.errors, [])
                self.context.close()
        self.context = self.browser.new_context()

    def test_bodyparts3d_credit_stays_when_only_the_vessel_file_is_missing(self):
        # 肝の区域は解剖データ側に入っている BodyParts3D 由来なので、血管のファイルだけ読めなくても表記は残す（CC BY 4.0）
        self.errors = []
        self.context = self.browser.new_context(viewport={'width': 1400, 'height': 900})
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(f'main: {error}'))
        self.page.route('**/data/bodyparts3d/liver_vessels.json', lambda route: route.fulfill(status=404, body='missing'))
        self.page.goto(self.base + '/web?anatomy=atlas')
        for _ in range(100):
            if self.page.evaluate('() => ATLAS.ready || ATLAS.failed'):
                break
            self.page.wait_for_timeout(100)
        self.page.wait_for_timeout(200)
        self.assertTrue(self.page.evaluate('ATLAS.ready'))
        self.assertFalse(self.page.evaluate('!!ATLAS.bodyParts3d'))
        credit = self.page.locator('#dataCredit')
        self.assertIn('BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International', credit.inner_text())
        self.assertEqual(credit.locator('a', has_text='CC BY 4.0').get_attribute('href'), 'https://creativecommons.org/licenses/by/4.0/')

    def test_switching_anatomy_back_and_forth_moves_the_current_probe_with_it(self):
        # 模式モデル→実CT→模式モデルと切り替えても、表示中の教本断面の位置・角度が、そのときの解剖の定位置に一致する。
        self.open_atlas()
        self.page.evaluate("selectTextbookView('liver_ic', 'post')")
        atlas_view = self.page.evaluate("() => [state.px, state.py, state.yaw, state.pitch, state.roll, ZONE_PROBE_BASES.right_intercostal.depth]")
        self.page.evaluate("() => { anatomyMode = 'model'; refreshAnatomy(); }")
        model_view = self.page.evaluate("() => [state.px, state.py, state.yaw, state.pitch, state.roll, ZONE_PROBE_BASES.right_intercostal.depth]")
        self.assertEqual(model_view, [-6.1, 0.5, 50, -9, 25, 4.5])
        self.assertEqual(self.page.evaluate("TEXTBOOK_VIEWS.liver_hv.pos"), [-0.6, 0.2])
        self.page.evaluate("() => { anatomyMode = 'atlas'; refreshAnatomy(); }")
        self.assertEqual(self.page.evaluate("() => [state.px, state.py, state.yaw, state.pitch, state.roll, ZONE_PROBE_BASES.right_intercostal.depth]"), atlas_view)
        self.assertEqual([round(v, 2) for v in atlas_view], [-5.95, 4.8, 28.6, -11.9, 22.0, 7.86])

    def test_atlas_data_and_license_are_served(self):
        self.open_atlas()
        for path, needle in (('/data/spl-abdominal-atlas/abdomen_labels.json', 'voxel_cm'),
                             ('/data/spl-abdominal-atlas/LICENSE-SPL-ABDOMINAL-ATLAS.txt', 'All or portions of this licensed product'),
                             ('/data/bodyparts3d/liver_vessels.json', 'lpvUmb'),
                             ('/data/bodyparts3d/LICENSE-BODYPARTS3D.txt', 'CC Attribution 4.0 International')):
            with self.subTest(path=path):
                response = self.page.request.get(self.base + path)
                self.assertEqual(response.status, 200)
                self.assertIn(needle, response.text())


if __name__ == '__main__':
    unittest.main()
