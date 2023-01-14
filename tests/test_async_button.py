# SPDX-FileCopyrightText: Copyright (c) 2023 Phil Underwood for Underwood Underground
#
# SPDX-License-Identifier: MIT
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, MagicMock
import sys
import asyncio

import microcontroller
import keypad

sys.modules["countio"] = MagicMock()

# pylint: disable=wrong-import-position
import async_button


class TestButton(IsolatedAsyncioTestCase):
    # pylint: disable=invalid-name, too-many-public-methods
    def setUp(self) -> None:
        self.time = MagicMock()
        self.patch1 = patch("async_button.time", new=self.time)
        self.patch1.start()
        self.time.monotonic.side_effect = self.new_monotonic
        self.keypad_keys = MagicMock()
        self.patch2 = patch("async_button.keypad.Keys", new=self.keypad_keys)
        self.patch2.start()
        self.keys = MagicMock()
        self.keypad_keys.return_value = self.keys
        self.keys.events.get_into = self.new_key_get
        self.button = None
        self.time_count = 0
        self.interval = 0.01
        self.button_timings = []
        self.button_state = False
        self.pin = microcontroller.Pin(0)

    async def asyncTearDown(self) -> None:
        self.patch1.stop()
        self.patch2.stop()
        if self.button:
            await asyncio.sleep(0)
            self.button.deinit()
            await asyncio.sleep(0)

    def new_monotonic(self) -> float:
        return self.time_count

    def new_key_get(self, event: keypad.Event) -> bool:
        self.time_count += self.interval
        if self.button_timings:
            if self.button_timings[0] <= self.time_count:
                self.button_state = not self.button_state
                self.button_timings.pop(0)
                # pylint: disable=protected-access
                event._pressed = self.button_state
                return True
        return False

    async def timeout(self):
        while True:
            if self.time_count > 10:
                raise TimeoutError
            await asyncio.sleep(0)

    async def wait_event_with_timeout(self, events):
        timeout = asyncio.create_task(self.timeout())
        button_wait = asyncio.create_task(self.button.wait(events))
        try:
            for coro in asyncio.as_completed((timeout, button_wait)):
                return await coro
        finally:
            timeout.cancel()
            button_wait.cancel()

    async def test_create_active_high(self):
        self.button = async_button.Button(self.pin, True)
        self.keypad_keys.assert_called_once_with(
            (self.pin,), value_when_pressed=True, pull=True
        )

    async def test_create_active_low(self):
        self.button = async_button.Button(self.pin, False)
        self.keypad_keys.assert_called_once_with(
            (self.pin,), value_when_pressed=False, pull=True
        )

    async def test_create_pull_false(self):
        self.button = async_button.Button(self.pin, True, pull=False)
        self.keypad_keys.assert_called_once_with(
            (self.pin,), value_when_pressed=True, pull=False
        )

    async def test_create_with_triple_but_no_double_fails(self):
        with self.assertRaises(ValueError):
            self.button = async_button.Button(
                self.pin, False, double_click_enable=False, triple_click_enable=True
            )

    async def test_button_pressed(self):
        self.button = async_button.Button(self.pin, True)
        self.button_timings = [0.10]
        await self.wait_event_with_timeout([async_button.Button.PRESSED])
        self.assertAlmostEqual(self.time_count, 0.10, delta=0.05)

    async def test_button_released(self):
        self.button = async_button.Button(self.pin, True)
        self.button_timings = [0.10, 0.20]
        await self.wait_event_with_timeout([async_button.Button.RELEASED])
        self.assertAlmostEqual(self.time_count, 0.20, delta=0.05)

    async def test_single_click(self):
        self.button = async_button.Button(self.pin, True)
        self.button_timings = [0.10, 0.20]
        await self.wait_event_with_timeout([async_button.Button.SINGLE])
        self.assertAlmostEqual(self.time_count, 0.20, delta=0.05)

    async def test_double_click(self):
        self.button = async_button.Button(self.pin, True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7]
        await self.wait_event_with_timeout([async_button.Button.DOUBLE])
        self.assertAlmostEqual(self.time_count, 0.70, delta=0.05)

    async def test_double_click_not_when_disabled(self):
        self.button = async_button.Button(self.pin, True, double_click_enable=False)
        self.button_timings = [0.10, 0.30, 0.5, 0.7]
        with self.assertRaises(TimeoutError):
            await self.wait_event_with_timeout([async_button.Button.DOUBLE])

    async def test_double_click_not_when_too_slow(self):
        self.button = async_button.Button(
            self.pin,
            True,
        )
        self.button_timings = [0.10, 0.30, 1.1, 1.3]
        with self.assertRaises(TimeoutError):
            await self.wait_event_with_timeout([async_button.Button.DOUBLE])

    async def test_two_singles_when_too_slow(self):
        self.button = async_button.Button(
            self.pin,
            True,
        )
        self.button_timings = [0.10, 0.30, 1.1, 1.3]
        await self.wait_event_with_timeout([async_button.Button.SINGLE])
        await self.wait_event_with_timeout([async_button.Button.SINGLE])

    async def test_double_click_not_when_too_slow_with_different_time(self):
        self.button = async_button.Button(self.pin, True, double_click_max_duration=0.1)
        self.button_timings = [0.10, 0.30, 0.5, 0.7]
        with self.assertRaises(TimeoutError):
            await self.wait_event_with_timeout([async_button.Button.DOUBLE])

    async def test_triple_click(self):
        self.button = async_button.Button(self.pin, True, triple_click_enable=True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        await self.wait_event_with_timeout([async_button.Button.TRIPLE])
        self.assertAlmostEqual(self.time_count, 1.1, delta=0.05)

    async def test_triple_click_not_when_disabled(self):
        self.button = async_button.Button(self.pin, True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        with self.assertRaises(TimeoutError):
            await self.wait_event_with_timeout([async_button.Button.TRIPLE])

    async def test_long_click(self):
        self.button = async_button.Button(self.pin, True, long_click_enable=True)
        self.button_timings = [0.10, 3.30]
        await self.wait_event_with_timeout([async_button.Button.LONG])
        self.assertAlmostEqual(self.time_count, 2.1, delta=0.1)

    async def test_long_click_not_when_disabled(self):
        self.button = async_button.Button(self.pin, True, long_click_enable=False)
        self.button_timings = [0.10, 2.30]
        with self.assertRaises(TimeoutError):
            await self.wait_event_with_timeout([async_button.Button.LONG])

    async def test_single_then_double_then_triple_works(self):
        self.button = async_button.Button(self.pin, True, triple_click_enable=True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        await self.wait_event_with_timeout([async_button.Button.SINGLE])
        await self.wait_event_with_timeout([async_button.Button.DOUBLE])
        await self.wait_event_with_timeout([async_button.Button.TRIPLE])
        self.assertAlmostEqual(self.time_count, 1.10, delta=0.05)

    async def test_wait_for_clicks(self):
        self.button = async_button.Button(self.pin, True, triple_click_enable=True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        self.assertEqual(await self.button.wait_for_click(), self.button.SINGLE)
        self.assertEqual(await self.button.wait_for_click(), self.button.DOUBLE)
        self.assertEqual(await self.button.wait_for_click(), self.button.TRIPLE)
        self.assertAlmostEqual(self.time_count, 1.10, delta=0.05)

    async def test_wait_for_clicks_goes_back_to_single(self):
        self.button = async_button.Button(self.pin, True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        self.assertEqual(await self.button.wait_for_click(), self.button.SINGLE)
        self.assertEqual(await self.button.wait_for_click(), self.button.DOUBLE)
        self.assertEqual(await self.button.wait_for_click(), self.button.SINGLE)
        self.assertAlmostEqual(self.time_count, 1.10, delta=0.05)

    async def test_wait_selection(self):
        self.button = async_button.Button(self.pin, True)
        selection = (self.button.SINGLE, self.button.PRESSED)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        self.assertSequenceEqual(
            await self.button.wait(selection), (self.button.PRESSED,)
        )
        self.assertSequenceEqual(
            await self.button.wait(selection), (self.button.SINGLE,)
        )
        self.assertSequenceEqual(
            await self.button.wait(selection), (self.button.PRESSED,)
        )
        self.assertSequenceEqual(
            await self.button.wait(selection), (self.button.PRESSED,)
        )
        self.assertSequenceEqual(
            await self.button.wait(selection), (self.button.SINGLE,)
        )
        self.assertAlmostEqual(self.time_count, 1.10, delta=0.05)

    async def test_wait_all(self):
        self.button = async_button.Button(self.pin, True, triple_click_enable=True)
        self.button_timings = [0.10, 0.30, 0.5, 0.7, 0.9, 1.1]
        self.assertSequenceEqual(await self.button.wait(), (self.button.PRESSED,))
        self.assertSequenceEqual(
            await self.button.wait(), (self.button.RELEASED, self.button.SINGLE)
        )
        self.assertSequenceEqual(await self.button.wait(), (self.button.PRESSED,))
        self.assertSequenceEqual(
            await self.button.wait(), (self.button.RELEASED, self.button.DOUBLE)
        )
        self.assertSequenceEqual(await self.button.wait(), (self.button.PRESSED,))
        self.assertSequenceEqual(
            await self.button.wait(), (self.button.RELEASED, self.button.TRIPLE)
        )
        self.assertAlmostEqual(self.time_count, 1.10, delta=0.05)
