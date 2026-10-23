"""
Smart Audio Focus for Windows
智能音频焦点与自动暂停/恢复脚本 (支持防抖与平滑淡入)
Author: tianchaoyamen
License: MIT
"""

import os
import sys
import json
import time
import asyncio
import logging
import ctypes
from typing import Dict, List, Optional, Tuple

# 保证控制台 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import comtypes
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation, ISimpleAudioVolume
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSession as MediaSession,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
)

# ----------------- 日志配置 -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SmartAudioFocus")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Windows 全局多媒体键代码 (备用兜底)
VK_MEDIA_PLAY_PAUSE = 0xB3


def send_global_media_play_pause():
    """发送全局多媒体暂停/播发键 (作为 SMTC 无法控制时的兜底手段)"""
    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)  # KEYEVENTF_KEYUP = 2
    except Exception as e:
        logger.debug(f"发送按键事件失败: {e}")


def load_config() -> dict:
    default_config = {
        "browser_processes": [
            "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
            "opera.exe", "vivaldi.exe", "arc.exe", "360chrome.exe",
            "sogouexplorer.exe", "qqbrowser.exe"
        ],
        "player_processes": [
            "foobar2000.exe", "cloudmusic.exe", "qqmusic.exe", "spotify.exe",
            "potplayer64.exe", "potplayer.exe", "vlc.exe", "aimp.exe",
            "musicbee.exe", "yesplaymusic.exe", "kugou.exe", "kwmusic.exe",
            "apple music.exe"
        ],
        "resume_delay_seconds": 2.0,
        "fade_in_duration_seconds": 1.5,
        "fade_in_steps": 15,
        "peak_threshold": 0.003,
        "poll_interval_seconds": 0.15,
        "session_refresh_interval_seconds": 3.0
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            logger.warning(f"读取配置文件失败，使用默认配置: {e}")
    return default_config


class SmartAudioFocus:
    def __init__(self):
        self.config = load_config()
        self.browsers = set(p.lower() for p in self.config["browser_processes"])
        self.players = set(p.lower() for p in self.config["player_processes"])
        
        self.resume_delay = float(self.config["resume_delay_seconds"])
        self.fade_duration = float(self.config["fade_in_duration_seconds"])
        self.fade_steps = int(self.config["fade_in_steps"])
        self.peak_threshold = float(self.config["peak_threshold"])
        self.poll_interval = float(self.config["poll_interval_seconds"])
        self.refresh_interval = float(self.config["session_refresh_interval_seconds"])

        # 缓存的 WASAPI 音频会话
        self.browser_meters: List[Tuple[str, IAudioMeterInformation]] = []
        self.player_volumes: Dict[str, ISimpleAudioVolume] = {}
        self.last_refresh_time = 0.0

        # SMTC 管理器
        self.smtc_manager: Optional[MediaManager] = None

        # 状态机
        self.is_paused_by_browser = False
        self.silence_start_time: Optional[float] = None
        self.paused_player_name: Optional[str] = None
        self.paused_player_original_vol: float = 1.0
        self.active_smtc_player_session: Optional[MediaSession] = None
        self.used_fallback_key = False

    def refresh_audio_sessions(self):
        """刷新 WASAPI 音频会话缓存，降低高频 COM 查询开销"""
        try:
            sessions = AudioUtilities.GetAllSessions()
            new_browser_meters = []
            new_player_volumes = {}

            for s in sessions:
                p = s.Process
                if not p:
                    continue
                try:
                    pname = p.name().lower()
                except Exception:
                    continue

                if pname in self.browsers:
                    try:
                        meter = s._ctl.QueryInterface(IAudioMeterInformation)
                        new_browser_meters.append((pname, meter))
                    except Exception:
                        pass
                elif pname in self.players:
                    try:
                        vol = s.SimpleAudioVolume
                        new_player_volumes[pname] = vol
                    except Exception:
                        pass

            self.browser_meters = new_browser_meters
            self.player_volumes = new_player_volumes
            self.last_refresh_time = time.time()
        except Exception as e:
            logger.debug(f"刷新音频会话异常: {e}")

    def get_max_browser_peak(self) -> Tuple[float, Optional[str]]:
        """获取所有监控中的浏览器当前最大峰值音量"""
        max_peak = 0.0
        active_proc = None
        dead_session = False

        for pname, meter in self.browser_meters:
            try:
                peak = meter.GetPeakValue()
                if peak > max_peak:
                    max_peak = peak
                    active_proc = pname
            except Exception:
                dead_session = True

        if dead_session or (time.time() - self.last_refresh_time > self.refresh_interval):
            self.refresh_audio_sessions()

        return max_peak, active_proc

    async def get_smtc_sessions(self) -> List[MediaSession]:
        """获取当前系统所有 SMTC 媒体会话"""
        if not self.smtc_manager:
            try:
                self.smtc_manager = await MediaManager.request_async()
            except Exception as e:
                logger.debug(f"获取 SMTC 管理器异常: {e}")
                return []
        try:
            return list(self.smtc_manager.get_sessions())
        except Exception:
            return []

    async def find_playing_player(self) -> Optional[Tuple[str, Optional[MediaSession]]]:
        """检测当前正在播放的本地音乐播放器会话"""
        # 1. 优先通过 SMTC 精确检测
        sessions = await self.get_smtc_sessions()
        for s in sessions:
            try:
                app_id = s.source_app_user_model_id.lower()
                status = s.get_playback_info().playback_status
                if status == PlaybackStatus.PLAYING:
                    for player in self.players:
                        if player in app_id:
                            return player, s
            except Exception:
                continue

        # 2. 如果 SMTC 没拿到，检查 WASAPI 中播放器是否有会话
        for pname in self.player_volumes.keys():
            if pname in self.players:
                return pname, None

        return None

    async def pause_player(self, player_name: str, session: Optional[MediaSession]):
        """暂停指定的播放器，并记录原音量"""
        logger.info(f"⏸️ 检测到网页声音，正在暂停本地播放器: {player_name}")
        
        # 记录原音量
        vol_ctrl = self.player_volumes.get(player_name)
        if vol_ctrl:
            try:
                self.paused_player_original_vol = vol_ctrl.GetMasterVolume()
            except Exception:
                self.paused_player_original_vol = 1.0
        else:
            self.paused_player_original_vol = 1.0

        paused_ok = False
        if session:
            try:
                paused_ok = await session.try_pause_async()
                self.used_fallback_key = False
            except Exception as e:
                logger.debug(f"SMTC 暂停失败: {e}")

        # 如果没有 SMTC 或 SMTC 失败，采用多媒体键
        if not paused_ok:
            send_global_media_play_pause()
            paused_ok = True
            self.used_fallback_key = True

        if paused_ok:
            self.is_paused_by_browser = True
            self.paused_player_name = player_name
            self.active_smtc_player_session = session
            self.silence_start_time = None
            logger.info(f"✅ {player_name} 已成功暂停 (原音量: {int(self.paused_player_original_vol * 100)}%)")

    async def resume_player_with_fade_in(self):
        """恢复播放并执行平滑淡入"""
        if not self.paused_player_name:
            self.is_paused_by_browser = False
            return

        player_name = self.paused_player_name
        session = self.active_smtc_player_session
        orig_vol = max(self.paused_player_original_vol, 0.1)

        logger.info(f"▶️ 网页已静默满 {self.resume_delay} 秒，正在恢复播放: {player_name} (平滑淡入至 {int(orig_vol*100)}%)")

        vol_ctrl = self.player_volumes.get(player_name)
        if vol_ctrl:
            try:
                # 1. 恢复前先将音量拉到 0
                vol_ctrl.SetMasterVolume(0.0, None)
            except Exception as e:
                logger.warning(f"设置初始音量 0 失败: {e}")

        # 2. 发送恢复播放指令
        resumed = False
        if session and not self.used_fallback_key:
            try:
                resumed = await session.try_play_async()
            except Exception as e:
                logger.debug(f"SMTC 恢复失败: {e}")

        if not resumed:
            send_global_media_play_pause()

        # 3. 执行平滑淡入 (由 0% 渐变至 orig_vol)
        if vol_ctrl and self.fade_duration > 0:
            step_sleep = self.fade_duration / max(self.fade_steps, 1)
            for step in range(1, self.fade_steps + 1):
                await asyncio.sleep(step_sleep)
                current_vol = orig_vol * (step / self.fade_steps)
                try:
                    vol_ctrl.SetMasterVolume(current_vol, None)
                except Exception:
                    break
            # 最终复原原音量
            try:
                vol_ctrl.SetMasterVolume(orig_vol, None)
            except Exception:
                pass
            logger.info(f"✨ {player_name} 淡入完成，音量已恢复至 {int(orig_vol*100)}%。")
        else:
            logger.info(f"✨ {player_name} 已恢复播放。")

        # 状态重置
        self.is_paused_by_browser = False
        self.paused_player_name = None
        self.active_smtc_player_session = None
        self.silence_start_time = None
        self.used_fallback_key = False

    async def run(self):
        """主监听轮询任务"""
        comtypes.CoInitialize()
        self.refresh_audio_sessions()
        logger.info("=" * 60)
        logger.info("🎵 Smart Audio Focus - 智能音频焦点管理服务已启动")
        logger.info(f"👀 监听浏览器: {', '.join(sorted(self.browsers))}")
        logger.info(f"🎧 监控播放器: {', '.join(sorted(self.players))}")
        logger.info(f"⏱️ 网页静默等待: {self.resume_delay} 秒 | 🎶 恢复淡入时长: {self.fade_duration} 秒")
        logger.info("=" * 60)

        try:
            while True:
                peak, active_proc = self.get_max_browser_peak()
                browser_is_playing = (peak >= self.peak_threshold)

                if browser_is_playing:
                    # 网页正在发声
                    self.silence_start_time = None
                    if not self.is_paused_by_browser:
                        # 查找是否有正在播放的音乐
                        playing = await self.find_playing_player()
                        if playing:
                            pname, s = playing
                            await self.pause_player(pname, s)
                else:
                    # 网页无声音
                    if self.is_paused_by_browser:
                        now = time.time()
                        if self.silence_start_time is None:
                            self.silence_start_time = now
                            logger.info(f"⏳ 网页声音已停止，开始防抖计时 {self.resume_delay} 秒...")
                        
                        elapsed = now - self.silence_start_time
                        if elapsed >= self.resume_delay:
                            # 倒计时完成，触发恢复与淡入
                            await self.resume_player_with_fade_in()

                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            pass
        finally:
            # 退出清理
            if self.paused_player_name and self.paused_player_name in self.player_volumes:
                try:
                    self.player_volumes[self.paused_player_name].SetMasterVolume(
                        self.paused_player_original_vol, None
                    )
                except Exception:
                    pass
            comtypes.CoUninitialize()
            logger.info("🛑 Smart Audio Focus 已安全退出。")


def main():
    try:
        asyncio.run(SmartAudioFocus().run())
    except KeyboardInterrupt:
        logger.info("\n收到退出信号，服务终止。")


if __name__ == "__main__":
    main()
