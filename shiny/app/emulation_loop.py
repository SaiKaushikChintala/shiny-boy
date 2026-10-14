import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiny.app.window import Viewer

GBA_FPS = 59.7275
FRAME_HISTORY = 120
FAST_BATCH_SECONDS = 0.03
INFO_UPDATE_EVERY_N_FRAMES = 6
HISTORY_MAX_SPEED = 8
TICK_IDLE_MS = 20


class EmulationLoop:
    def __init__(self, app: "Viewer"):
        self.app = app
        self.history: deque[tuple[bytes, int]] = deque(maxlen=FRAME_HISTORY)
        self.paused = False
        self.user_paused = False
        self.frames_since_info_update = 0
        self.fps = 0.0
        self.video_on = True
        self.fps_frames = 0
        self.fps_since = time.perf_counter()
        self.last_frame_time = time.perf_counter()

    def restart_clock(self) -> None:
        self.last_frame_time = time.perf_counter()


    def toggle_pause(self) -> None:
        self.user_paused = not self.user_paused
        self.app.paused_variable.set(self.user_paused)
        self.apply_pause()

    def toggle_pause_from_menu(self) -> None:
        self.user_paused = self.app.paused_variable.get()
        self.apply_pause()

    def apply_pause(self) -> None:
        app = self.app
        app.toolbar.set_paused(self.user_paused)
        if self.user_paused:
            app.pause_badge.place(relx=0.5, y=18, anchor="n")
            app.pause_badge.lift()
            app.set_status("Paused.")
        else:
            app.pause_badge.place_forget()
            self.restart_clock()
            app.set_status("Resumed.")
        app.focus_game()

    def _show_video(self) -> None:
        if not self.video_on:
            self.app.emulator.set_video_enabled(True)
            self.video_on = True

    def step_forward(self) -> None:
        app = self.app
        if app.bots.is_active():
            return
        if not self.user_paused:
            self.toggle_pause()
        self._show_video()
        self.history.append((app.emulator.get_state(), app.pressed))
        app.emulator.set_keys(app.pressed)
        app.emulator.run_frame()
        app.emulator.read_audio()
        self._after_step()

    def step_back(self) -> None:
        app = self.app
        if app.bots.is_active():
            return
        if not self.user_paused:
            self.toggle_pause()
        if len(self.history) < 2:
            app.set_status("No earlier frame is kept (the last two seconds or so are).", "warning")
            return
        self.history.pop()
        state, keys = self.history[-1]
        app.emulator.set_state(state)
        self._show_video()
        app.emulator.set_keys(keys)
        app.emulator.run_frame()
        app.emulator.read_audio()
        self._after_step()

    def _after_step(self) -> None:
        self.app.draw_screen()
        self.app.update_info()
        self.app.set_status(f"Frame {self.app.emulator.frame_count:,}.")

    def on_speed_changed(self) -> None:
        speed = self.app.speed_variable.get()
        self.app.set_status("Speed: maximum (no sound)." if speed == 0 else f"Speed: {speed}×" + ("" if speed == 1 else " (no sound)."))
        self.restart_clock()
        self.app.focus_game()


    def frame_budget(self, replay_fast: bool) -> tuple[int, float | None]:
        speed = self.app.speed_variable.get()
        if replay_fast or speed == 0:
            return 1_000_000, FAST_BATCH_SECONDS
        if speed >= 16:
            return int(speed * GBA_FPS * FAST_BATCH_SECONDS) + 1, FAST_BATCH_SECONDS
        return speed, None

    def tick(self) -> None:
        app = self.app
        bots = app.bots
        if self.paused or self.user_paused or bots.state in ("hunting", "listing"):
            app.window.after(TICK_IDLE_MS, self.tick)
            return

        replay_fast = bots.state == "replaying" and app.bot_panel.fast_replay
        frames_wanted, time_box = self.frame_budget(replay_fast)
        deadline = None if time_box is None else time.perf_counter() + time_box
        frames_run = 0
        pcm = b""
        for _ in range(frames_wanted):
            keys = app.pressed
            if bots.state == "replaying":
                keys = bots.next_replay_keys()
                if keys is None:
                    break
            if deadline is not None:
                is_last = frames_run + 1 >= frames_wanted or time.perf_counter() >= deadline
                if is_last != self.video_on:
                    app.emulator.set_video_enabled(is_last)
                    self.video_on = is_last
            else:
                self._show_video()
            if bots.state is None and app.speed_variable.get() <= HISTORY_MAX_SPEED:
                self.history.append((app.emulator.get_state(), keys))
            app.emulator.set_keys(keys)
            app.emulator.run_frame()
            pcm = app.emulator.read_audio()
            frames_run += 1
            if deadline is not None and self.video_on:
                break

        if frames_run == 0:
            app.update_info()
            app.window.after(1, self.tick)
            return

        app.draw_screen()

        if bots.state == "replaying":
            app.bot_panel.set_progress(bots.replay_progress())

        self._track_speed(frames_run)
        self.frames_since_info_update += frames_run
        if self.frames_since_info_update >= INFO_UPDATE_EVERY_N_FRAMES:
            self.frames_since_info_update = 0
            app.update_info()

        self._pace(frames_run, pcm, replay_fast)
        self.restart_clock()
        app.window.after(1, self.tick)

    def _track_speed(self, frames_run: int) -> None:
        self.fps_frames += frames_run
        now = time.perf_counter()
        if now - self.fps_since >= 0.5:
            self.fps = self.fps_frames / (now - self.fps_since)
            self.fps_frames = 0
            self.fps_since = now

    def _pace(self, frames_run: int, pcm: bytes, replay_fast: bool) -> None:
        speed = self.app.speed_variable.get()
        if replay_fast or speed == 0:
            return
        if speed == 1 and frames_run == 1 and self.app.audio.available:
            self.app.audio.play(pcm, self.app.gain)
            return
        wait = frames_run / (GBA_FPS * speed) - (time.perf_counter() - self.last_frame_time)
        if wait > 0:
            time.sleep(wait)
